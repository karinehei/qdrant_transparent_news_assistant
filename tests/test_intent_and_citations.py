"""Test intent detection, citation format, and prompt leakage fixes."""
import pytest
from news_assistant.intent import detect_intent, sort_sources_by_timestamp
from news_assistant.citations import check_citation_coverage, SourceRef
from news_assistant.api import _remove_prompt_leakage, _validate_url


def test_latest_intent_detection():
    """Test that latest news intent is detected correctly."""
    is_latest, is_headlines = detect_intent("viimeinen uutinen")
    assert is_latest is True
    assert is_headlines is False
    
    is_latest, is_headlines = detect_intent("viimeisin uutinen")
    assert is_latest is True
    
    is_latest, is_headlines = detect_intent("uusin uutinen")
    assert is_latest is True
    
    is_latest, is_headlines = detect_intent("latest news")
    assert is_latest is True
    
    is_latest, is_headlines = detect_intent("Mitä uutisia on tänään?")
    assert is_latest is False


def test_sort_sources_by_timestamp():
    """Test sorting sources by timestamp."""
    hits = [
        {"payload": {"published_at": "2026-01-11T10:00:00", "title": "Newest"}},
        {"payload": {"published_at": "2026-01-10T10:00:00", "title": "Older"}},
        {"payload": {"published_at": "2026-01-09T10:00:00", "title": "Oldest"}},
    ]
    
    sorted_hits = sort_sources_by_timestamp(hits, reverse=True)
    assert sorted_hits[0]["payload"]["title"] == "Newest"
    assert sorted_hits[-1]["payload"]["title"] == "Oldest"
    
    # Test with missing timestamp (should be treated as oldest)
    hits_with_missing = [
        {"payload": {"title": "No timestamp"}},
        {"payload": {"published_at": "2026-01-11T10:00:00", "title": "Has timestamp"}},
    ]
    sorted_missing = sort_sources_by_timestamp(hits_with_missing, reverse=True)
    assert sorted_missing[0]["payload"]["title"] == "Has timestamp"


def test_citation_format_parentheses():
    """Test that audit recognizes (S1) format citations."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
        SourceRef(key="2", label="S2", title="Article 2", url="http://example.com/2", published_at=None, publisher=None),
    ]
    
    # Answer with parentheses format (correct)
    answer = "This is a fact (S1). Another fact (S2). Lähteet: - (S1) Article 1 — http://example.com/1"
    has_coverage, warnings = check_citation_coverage(answer, sources)
    # Should have coverage or minimal warnings
    assert len([w for w in warnings if "CRITICAL" in w]) == 0
    
    # Answer with brackets format (backward compatibility)
    answer_brackets = "This is a fact [S1]. Another fact [S2]."
    has_coverage_b, warnings_b = check_citation_coverage(answer_brackets, sources)
    # Should also work
    assert len([w for w in warnings_b if "CRITICAL" in w]) == 0


def test_prompt_leakage_removal():
    """Test that instruction text is removed from answers."""
    # Answer with leaked instructions
    answer_with_leakage = "Käytä suomeksi ja informatiivisesti. Tämä on vastaus."
    cleaned = _remove_prompt_leakage(answer_with_leakage)
    assert "Käytä suomeksi" not in cleaned
    assert "Tämä on vastaus" in cleaned
    
    # Answer with multiple instruction markers
    answer_multi = "VASTAUSOHJE: Vastaa suomeksi. Tämä on vastaus."
    cleaned_multi = _remove_prompt_leakage(answer_multi)
    assert "VASTAUSOHJE" not in cleaned_multi
    assert "Vastaa suomeksi" not in cleaned_multi
    
    # Normal answer (no leakage)
    normal_answer = "Tämä on normaali vastaus ilman ohjeita."
    cleaned_normal = _remove_prompt_leakage(normal_answer)
    assert cleaned_normal == normal_answer


def test_url_validation():
    """Test URL validation."""
    assert _validate_url("https://example.com") is True
    assert _validate_url("http://example.com") is True
    assert _validate_url("https://") is True  # Technically valid start
    assert _validate_url("example.com") is False
    assert _validate_url("") is False
    assert _validate_url("ftp://example.com") is False


def test_audit_ignores_procedural_sentences():
    """Test that audit ignores procedural sentences and headings."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
    ]
    
    # Answer with procedural sentence (should not require citation)
    answer = "Tässä viimeisin uutinen: Tämä on fakta (S1). Lähteet: - (S1) Article 1"
    has_coverage, warnings = check_citation_coverage(answer, sources)
    # Procedural sentence "Tässä viimeisin uutinen:" should not trigger citation requirement
    assert len([w for w in warnings if "CRITICAL" in w]) == 0
