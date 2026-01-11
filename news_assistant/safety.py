import re
from typing import Iterable

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+all\s+instructions",
    r"system\s+prompt",
    r"developer\s+message",
    r"you\s+are\s+chatgpt",
    r"do\s+not\s+cite",
    r"reveal.*(keys|secrets|prompt)",
]

def looks_like_prompt_injection(text: str) -> bool:
    t = text.lower()
    # Check each pattern
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            return True
    return False


def sanitize_context(text: str) -> str:
    # Keep it simple: strip excessive whitespace and truncate very long chunks
    t = re.sub(r"\s+", " ", text).strip()
    return t[:1500]


def any_context_is_suspicious(texts: Iterable[str]) -> bool:
    return any(looks_like_prompt_injection(t) for t in texts)
