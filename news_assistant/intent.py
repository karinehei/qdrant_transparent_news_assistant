"""Intent detection and topic extraction for user queries."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

_MIN_AWARE = datetime.min.replace(tzinfo=UTC)

LATEST_INTENT_PATTERNS = [
    r"\bviimeinen\s+uutinen\b",
    r"\bviimeisin\s+uutinen\b",
    r"\buusin\s+uutinen\b",
    r"\blatest\s+news\b",
    r"\bmost\s+recent\b",
    r"\bviimeisin\b",
    r"\buusin\b",
]

HEADLINES_INTENT_PATTERNS = [
    r"\buutiset\b",
    r"\bheadlines\b",
    r"\botsikot\b",
    r"\buseita\s+uutisia\b",
    r"\buseita\s+uutista\b",
]

# Stopwords to remove when extracting topics
STOPWORDS_FI = {
    "uutiset",
    "uutisia",
    "uutinen",
    "uutista",
    "uutisista",
    "aiheesta",
    "aihe",
    "aihetta",
    "aiheista",
    "tietoa",
    "tietoja",
    "tieto",
    "tiedot",
    "kerro",
    "kerrotaan",
    "kerrota",
    "kerrottu",
    "mitä",
    "mistä",
    "missä",
    "miksi",
    "milloin",
    "on",
    "oli",
    "ovat",
    "ole",
    "olen",
    "ja",
    "tai",
    "sekä",
    "mutta",
    "vain",
    "the",
    "a",
    "an",
    "and",
    "or",
    "about",
    "news",
    "latest",
    "most",
    "recent",
}

STOPWORDS_EN = {
    "news",
    "about",
    "latest",
    "most",
    "recent",
    "headlines",
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "in",
    "on",
    "at",
    "to",
    "for",
}


@dataclass
class QueryIntent:
    """Structured query intent information."""

    intent: str  # "latest" | "topic" | "general"
    topic: str | None = None  # Extracted topic string (e.g., "terveys", "talous")
    geo: str | None = None  # Extracted geographic filter (e.g., "FI" for Finland)
    original_query: str = ""


def extract_topic(query: str) -> str | None:
    """
    Extract topic from query patterns like "uutiset <X>", "uutisia <X>", "<X> uutiset".

    Returns:
        Topic string or None if no topic detected
    """
    query_lower = query.lower().strip()
    query_original = query.strip()

    # Pattern 1: "uutiset <topic>" / "uutisia <topic>"
    match = re.search(r"uutiset\s+(.+?)(?:\s|$)", query_lower, re.IGNORECASE)
    if match:
        # Extract from original query to preserve case
        start, end = match.span(1)
        topic = query_original[start:end].strip()
        # Remove trailing punctuation and stopwords
        topic = re.sub(r"[.,!?;:]+$", "", topic)
        if topic and topic.lower() not in STOPWORDS_FI:
            return topic

    # Pattern 2: "<topic> uutiset" / "<topic> uutisia"
    match = re.search(r"^(.+?)\s+uutiset", query_lower, re.IGNORECASE)
    if match:
        start, end = match.span(1)
        topic = query_original[start:end].strip()
        topic = re.sub(r"[.,!?;:]+$", "", topic)
        if topic and topic.lower() not in STOPWORDS_FI:
            return topic

    # Pattern 3: "news about <topic>" / "news on <topic>"
    # Use non-greedy match but capture until end of string or next major punctuation
    match = re.search(r"news\s+(?:about|on|regarding)\s+(.+?)(?:[.!?]|$)", query_lower, re.IGNORECASE)
    if match:
        start, end = match.span(1)
        topic = query_original[start:end].strip()
        # Remove trailing punctuation and stopwords, but preserve multi-word topics
        topic = re.sub(r"[.,!?;:]+$", "", topic)
        if topic and topic.lower() not in STOPWORDS_EN:
            return topic

    # Pattern 4: "aihe: <topic>" / "topic: <topic>"
    match = re.search(r"(?:aihe|topic):\s*(.+?)(?:\s|$)", query_lower, re.IGNORECASE)
    if match:
        start, end = match.span(1)
        topic = query_original[start:end].strip()
        topic = re.sub(r"[.,!?;:]+$", "", topic)
        if topic:
            return topic

    return None


def detect_intent(query: str) -> tuple[bool, bool]:
    """
    Detect user intent from query.

    Returns:
        (is_latest_intent, is_headlines_intent)
    """
    query_lower = query.lower()

    is_latest = any(re.search(pattern, query_lower) for pattern in LATEST_INTENT_PATTERNS)
    is_headlines = any(re.search(pattern, query_lower) for pattern in HEADLINES_INTENT_PATTERNS)

    return is_latest, is_headlines


def extract_geo(query: str) -> str | None:
    """
    Extract geographic filter from query.

    Returns:
        Geographic code (e.g., "FI" for Finland) or None
    """
    query_lower = query.lower()

    # Finland patterns
    finland_patterns = [
        r"\bsuomi\b",
        r"\bsuomessa\b",
        r"\bsuomen\b",
        r"\bkotimaa\b",
        r"\bkotimaassa\b",
        r"\bfinland\b",
        r"\bfinnish\b",
    ]

    if any(re.search(pattern, query_lower) for pattern in finland_patterns):
        return "FI"

    return None


def parse_query_intent(query: str) -> QueryIntent:
    """
    Parse query to extract intent, topic, and geographic filter.

    Returns:
        QueryIntent with intent type, extracted topic, and geo filter
    """
    # Check for latest intent
    is_latest, is_headlines = detect_intent(query)

    # Extract geo
    geo = extract_geo(query)

    if is_latest:
        return QueryIntent(intent="latest", topic=None, geo=geo, original_query=query)

    # Extract topic
    topic = extract_topic(query)

    if topic:
        return QueryIntent(intent="topic", topic=topic, geo=geo, original_query=query)

    # Check for general headlines
    if is_headlines:
        return QueryIntent(intent="general", topic=None, geo=geo, original_query=query)

    # Default: general query
    return QueryIntent(intent="general", topic=None, geo=geo, original_query=query)


def sort_sources_by_timestamp(hits: list, reverse: bool = True) -> list:
    """
    Sort hits by published_at timestamp.

    Args:
        hits: List of hit dicts with payload containing published_at
        reverse: If True, newest first (default)

    Returns:
        Sorted list of hits
    """

    def get_timestamp(hit):
        payload = hit.get("payload", {})
        timestamp_str = payload.get("published_at")
        if not timestamp_str:
            # Missing timestamp = treat as oldest
            return _MIN_AWARE
        try:
            # Try ISO format first
            if "T" in timestamp_str:
                dt = datetime.fromisoformat(timestamp_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            # Try other formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(timestamp_str, fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue
            return _MIN_AWARE
        except (ValueError, AttributeError):
            return _MIN_AWARE

    return sorted(hits, key=get_timestamp, reverse=reverse)
