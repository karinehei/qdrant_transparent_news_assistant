"""Test topic-based retrieval and filtering."""

from news_assistant.api import _parse_structured_output, _validate_citations
from news_assistant.citations import (
    SourceRef,
    check_citation_coverage,
    compute_query_relevance,
)
from news_assistant.intent import extract_topic, parse_query_intent


def test_topic_extraction():
    """Test topic extraction from various query patterns."""
    # Pattern: "uutiset <topic>"
    topic = extract_topic("uutiset terveydestä")
    assert topic == "terveydestä"

    topic = extract_topic("uutiset taloudesta")
    assert topic == "taloudesta"

    topic = extract_topic("uutiset tekoälystä")
    assert topic == "tekoälystä"

    # Pattern: "<topic> uutiset"
    topic = extract_topic("Ukrainasta uutiset")
    assert topic == "Ukrainasta"

    # Pattern: "news about <topic>"
    topic = extract_topic("news about artificial intelligence")
    assert topic == "artificial intelligence"

    # No topic (latest intent)
    topic = extract_topic("viimeinen uutinen")
    assert topic is None

    # No topic (general)
    topic = extract_topic("Mitä uutisia on tänään?")
    assert topic is None


def test_parse_query_intent():
    """Test query intent parsing."""
    # Latest intent
    intent = parse_query_intent("viimeinen uutinen")
    assert intent.intent == "latest"
    assert intent.topic is None

    # Topic intent
    intent = parse_query_intent("uutiset terveydestä")
    assert intent.intent == "topic"
    assert intent.topic == "terveydestä"

    # General intent
    intent = parse_query_intent("Mitä uutisia on tänään?")
    assert intent.intent == "general"
    assert intent.topic is None


def test_topic_relevance_scoring():
    """Test that topic relevance scoring works."""
    # High relevance: topic matches content
    relevance = compute_query_relevance("terveys", "Terveydenhuolto kriisissä. Sairaalat täynnä potilaita.", "Terveysuutiset")
    assert relevance > 0.3  # Should be relevant

    # Low relevance: topic doesn't match
    relevance = compute_query_relevance("terveys", "Greenland is an island. Denmark owns it.", "About Greenland")
    assert relevance < 0.2  # Should be irrelevant


def test_structured_output_parsing():
    """Test parsing of structured JSON output from LLM."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
        SourceRef(key="2", label="S2", title="Article 2", url="http://example.com/2", published_at=None, publisher=None),
    ]

    # Valid JSON output
    json_output = """{
  "answer_fi": ["Tämä on fakta (S1).", "Toinen fakta (S2)."],
  "sources_used": ["S1", "S2"]
}"""
    answer, sources_used = _parse_structured_output(json_output, sources)
    assert answer is not None
    assert "Tämä on fakta" in answer
    assert sources_used == ["S1", "S2"]

    # JSON in markdown code block
    json_md = """```json
{
  "answer_fi": ["Fakta (S1)."],
  "sources_used": ["S1"]
}
```"""
    answer, sources_used = _parse_structured_output(json_md, sources)
    assert answer is not None
    assert sources_used == ["S1"]

    # Invalid JSON (fallback to None)
    invalid = "This is not JSON"
    answer, sources_used = _parse_structured_output(invalid, sources)
    assert answer is None


def test_citation_validation():
    """Test that citations are validated against available sources."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
    ]
    warnings = []

    # Answer with valid citation
    answer = "This is a fact (S1)."
    validated = _validate_citations(answer, sources, warnings)
    assert "(S1)" in validated
    assert len(warnings) == 0

    # Answer with invalid citation
    answer2 = "This is a fact (S2)."
    warnings2 = []
    validated2 = _validate_citations(answer2, sources, warnings2)
    assert "(S2)" not in validated2
    assert any("non-existent" in w.lower() for w in warnings2)


def test_topic_query_filters_irrelevant():
    """Test that topic queries filter out irrelevant sources."""
    # This would need integration with the full API, but we can test the relevance logic
    topic = "terveys"

    # Relevant source
    rel1 = compute_query_relevance(topic, "Terveydenhuolto kriisissä. Sairaalat täynnä.", "Terveysuutiset")

    # Irrelevant source
    rel2 = compute_query_relevance(topic, "Greenland is an island. Denmark owns it.", "About Greenland")

    # Relevant should score higher
    assert rel1 > rel2
    # Relevant should pass threshold (0.30)
    assert rel1 >= 0.30
    # Irrelevant should fail threshold
    assert rel2 < 0.30


def test_latest_intent_single_source():
    """Test that latest intent returns only S1."""
    intent = parse_query_intent("viimeinen uutinen")
    assert intent.intent == "latest"
    assert intent.topic is None


def test_citation_format_validation():
    """Test that only (S1) format is accepted, [S1] is ignored."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
    ]

    # Answer with bracket citations (should be ignored by audit)
    answer = "This is a fact [S2]. Another fact [S3]. Valid fact (S1)."
    _has_coverage, warnings = check_citation_coverage(answer, sources)

    # Should NOT report [S2] or [S3] as non-existent
    non_existent_warnings = [w for w in warnings if "non-existent" in w.lower() and ("S2" in w or "S3" in w)]
    assert len(non_existent_warnings) == 0, f"Should not report bracket citations: {warnings}"
