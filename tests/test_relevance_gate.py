"""Test relevance gate and citation enforcement."""
from news_assistant.citations import (
    check_answerability,
    check_citation_coverage,
    compute_query_relevance,
    SourceRef,
)


def test_compute_query_relevance():
    """Test query-to-source relevance computation."""
    # High relevance: query tokens match text
    relevance = compute_query_relevance(
        "usa ja kiina",
        "USA and China are major powers. They have trade relations.",
        "USA China Relations"
    )
    assert relevance > 0.5  # Should be high
    
    # Low relevance: query tokens don't match
    relevance = compute_query_relevance(
        "usa ja kiina",
        "Greenland is an island. Denmark owns it.",
        "About Greenland"
    )
    assert relevance < 0.3  # Should be low
    
    # Medium relevance: partial match
    relevance = compute_query_relevance(
        "usa ja kiina",
        "USA has trade policies. China is mentioned briefly.",
        "Trade Policies"
    )
    assert 0.2 < relevance < 0.6  # Should be medium


def test_relevance_gate_blocks_irrelevant_sources():
    """Regression test: 'usa ja kiina' query should NOT answer with Greenland/ICE sources."""
    # Simulate the bug scenario: query about USA/China, but retrieval returns Greenland/ICE
    hits = [
        {
            "score": 0.5,  # Vector score is OK
            "payload": {
                "text": "Greenland is a large island. Denmark owns Greenland. Trump mentioned Greenland.",
                "title": "Greenland and Denmark"
            }
        },
        {
            "score": 0.45,
            "payload": {
                "text": "ICE agent shot someone during arrest. Protests happened in streets.",
                "title": "ICE Shooting Incident"
            }
        },
    ]
    
    can_answer, reason = check_answerability(
        hits,
        query="usa ja kiina",  # User asks about USA and China
        score_threshold=0.25,  # Vector scores pass
        relevance_threshold=0.35,  # But relevance gate should block
        min_relevant_sources=1,
        use_relevance_gate=True,
    )
    
    # Should be blocked because sources are about Greenland/ICE, not USA/China
    assert not can_answer, f"Should reject irrelevant sources. Reason: {reason}"
    assert "relevant" in reason.lower() or "clarify" in reason.lower()


def test_relevance_gate_allows_relevant_sources():
    """Test that relevant sources pass the gate."""
    hits = [
        {
            "score": 0.6,
            "payload": {
                "text": "USA and China are major economic powers. Trade relations between USA and China are complex.",
                "title": "USA China Relations"
            }
        },
        {
            "score": 0.55,
            "payload": {
                "text": "China's economy. USA trade policies. Bilateral agreements.",
                "title": "Economic Relations"
            }
        },
    ]
    
    can_answer, reason = check_answerability(
        hits,
        query="usa ja kiina",
        score_threshold=0.25,
        relevance_threshold=0.35,
        min_relevant_sources=1,
        use_relevance_gate=True,
    )
    
    # Should pass because sources are relevant
    assert can_answer, f"Should accept relevant sources. Reason: {reason}"


def test_citation_enforcement_strict():
    """Test that answers without citations are flagged."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
        SourceRef(key="2", label="S2", title="Article 2", url="http://example.com/2", published_at=None, publisher=None),
    ]
    
    # Answer with NO citations (should fail)
    answer = "USA is a country. China is also a country. They have relations."
    has_coverage, warnings = check_citation_coverage(answer, sources)
    assert not has_coverage or any("uncited" in w.lower() for w in warnings)
    
    # Answer with SOME citations (partial coverage)
    answer = "USA is a country [S1]. China is also a country. They have relations [S2]."
    has_coverage, warnings = check_citation_coverage(answer, sources)
    # Should warn about uncited statement
    assert any("uncited" in w.lower() for w in warnings) or not has_coverage
    
    # Answer with ALL citations (good)
    answer = "USA is a country [S1]. China is also a country [S2]. They have relations [S1]. Lähteet: - [S1] Article 1, - [S2] Article 2"
    has_coverage, warnings = check_citation_coverage(answer, sources)
    # Should have better coverage (may still warn if Sources section format is off, but citations are there)
    assert len([w for w in warnings if "CRITICAL" in w]) == 0


def test_invalid_citation_detection():
    """Test that citations to non-existent sources are caught."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
    ]
    
    # Answer cites S2 which doesn't exist
    answer = "This is a fact [S2]. Another fact [S1]."
    has_coverage, warnings = check_citation_coverage(answer, sources)
    assert not has_coverage
    assert any("non-existent" in w.lower() or "CRITICAL" in w for w in warnings)
