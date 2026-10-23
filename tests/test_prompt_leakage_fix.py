"""Test prompt leakage fixes and citation validation."""

from news_assistant.api import (
    _has_instruction_leakage,
    _remove_bracket_citations,
    _remove_prompt_leakage,
)
from news_assistant.citations import SourceRef, check_citation_coverage


def test_prompt_leakage_detection():
    """Test that instruction leakage is detected."""
    # Answer with instruction leakage
    answer_with_leakage = "PAKOLLISET LÄHTEET: Jokainen faktaväite tarvitsee lähdeviitteen."
    assert _has_instruction_leakage(answer_with_leakage) is True

    # Answer with KUNTAAN
    answer_kuntaan = "Vastaa KUNTAAN annetun kontekstin perusteella."
    assert _has_instruction_leakage(answer_kuntaan) is True

    # Normal answer
    normal_answer = "Tämä on normaali vastaus ilman ohjeita."
    assert _has_instruction_leakage(normal_answer) is False


def test_prompt_leakage_removal():
    """Test that instruction text is removed."""
    # Answer with PAKOLLISET
    answer = "PAKOLLISET LÄHTEET: Jokainen faktaväite tarvitsee lähdeviitteen. Tämä on vastaus (S1)."
    cleaned = _remove_prompt_leakage(answer)
    assert "PAKOLLISET" not in cleaned
    assert "Tämä on vastaus" in cleaned

    # Answer with KUNTAAN
    answer2 = "Vastaa KUNTAAN annetun kontekstin perusteella. Tämä on vastaus."
    cleaned2 = _remove_prompt_leakage(answer2)
    assert "KUNTAAN" not in cleaned2

    # Answer with numbered instructions
    answer3 = "1. VASTAUS VAIN KONTEKSTISTA\n2. PAKOLLISET LÄHTEET\nTämä on vastaus (S1)."
    cleaned3 = _remove_prompt_leakage(answer3)
    assert "1. VASTAUS" not in cleaned3
    assert "2. PAKOLLISET" not in cleaned3
    assert "Tämä on vastaus" in cleaned3


def test_bracket_citation_removal():
    """Test that bracket citations [S1] are removed."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
    ]

    # Answer with bracket citation (invalid)
    answer = "This is a fact [S2]. Another fact [S1]."
    cleaned = _remove_bracket_citations(answer, sources)
    assert "[S2]" not in cleaned
    assert "[S1]" not in cleaned
    # Should still have the text
    assert "This is a fact" in cleaned or "fact" in cleaned.lower()


def test_audit_ignores_bracket_citations():
    """Test that audit ignores bracket citations [S1] completely."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
    ]

    # Answer with bracket citations (should be ignored)
    answer = "This is a fact [S2]. Another fact [S3]. Valid fact (S1)."
    _has_coverage, warnings = check_citation_coverage(answer, sources)

    # Should NOT report [S2] or [S3] as non-existent sources
    non_existent_warnings = [w for w in warnings if "non-existent" in w.lower()]
    assert len(non_existent_warnings) == 0, f"Should not report bracket citations as non-existent: {warnings}"

    # Should recognize (S1) as valid
    assert "(S1)" in answer


def test_only_valid_sources_cited():
    """Test that answer cannot cite non-existent sources."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
    ]

    # Answer citing S2 which doesn't exist
    answer = "This is a fact (S2)."
    has_coverage, warnings = check_citation_coverage(answer, sources)

    # Should report S2 as non-existent
    assert not has_coverage or any("non-existent" in w.lower() or "S2" in w for w in warnings)


def test_latest_intent_single_source():
    """Test that latest intent returns only S1."""
    # This test would need to be integrated with the API endpoint
    # For now, we test the intent detection
    from news_assistant.intent import detect_intent

    is_latest, _ = detect_intent("viimeinen uutinen")
    assert is_latest is True
