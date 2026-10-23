"""Test citation functionality."""

from news_assistant.citations import (
    SourceRef,
    assign_source_labels,
    check_answerability,
    check_citation_coverage,
)


def test_assign_source_labels():
    """Test source label assignment."""
    hits = [
        {"payload": {"source_id": "article1", "title": "Article 1", "url": "http://example.com/1"}},
        {"payload": {"source_id": "article1", "title": "Article 1", "url": "http://example.com/1"}},
        {"payload": {"source_id": "article2", "title": "Article 2", "url": "http://example.com/2"}},
    ]

    labeled_hits, sources = assign_source_labels(hits)

    assert len(sources) == 2
    assert sources[0].label == "S1"
    assert sources[1].label == "S2"
    assert all(h.get("source_label") in ["S1", "S2"] for h in labeled_hits)


def test_check_answerability():
    """Test answerability gate."""
    # No hits
    can_answer, reason = check_answerability([], query="test", score_threshold=0.3)
    assert not can_answer
    assert "No sources" in reason

    # Low score
    hits = [{"score": 0.1, "payload": {"text": "Some text", "title": "Title"}}]
    can_answer, reason = check_answerability(hits, query="test", score_threshold=0.3)
    assert not can_answer
    assert "confidence" in reason.lower()

    # Good hits with relevant content
    hits = [
        {"score": 0.8, "payload": {"text": "test content " * 20, "title": "Test Article"}},
        {"score": 0.7, "payload": {"text": "test data " * 20, "title": "Test Data"}},
    ]
    can_answer, reason = check_answerability(
        hits,
        query="test",
        score_threshold=0.3,
        use_relevance_gate=True,
        relevance_threshold=0.2,  # Lower threshold for test
    )
    assert can_answer

    # Irrelevant sources (regression test for "usa ja kiina" scenario)
    hits = [
        {"score": 0.5, "payload": {"text": "Greenland is an island. Denmark owns it.", "title": "About Greenland"}},
        {"score": 0.4, "payload": {"text": "ICE agent shot someone. Protests happened.", "title": "ICE Shooting"}},
    ]
    can_answer, reason = check_answerability(
        hits,
        query="usa ja kiina",  # Query about USA and China
        score_threshold=0.25,
        use_relevance_gate=True,
        relevance_threshold=0.35,  # Strict threshold
        min_relevant_sources=1,
    )
    # Should reject because sources are about Greenland/ICE, not USA/China
    assert not can_answer
    assert "relevant" in reason.lower() or "clarify" in reason.lower()


def test_check_citation_coverage():
    """Test citation coverage check."""
    sources = [
        SourceRef(key="1", label="S1", title="Article 1", url="http://example.com/1", published_at=None, publisher=None),
        SourceRef(key="2", label="S2", title="Article 2", url="http://example.com/2", published_at=None, publisher=None),
    ]

    # Good answer with citations
    answer = "This is a fact [S1]. Another fact [S2]. Lähteet: [S1] Article 1, [S2] Article 2"
    has_coverage, warnings = check_citation_coverage(answer, sources)
    assert has_coverage or len(warnings) == 0

    # Answer with invalid citation
    answer = "This is a fact [S3]."
    has_coverage, warnings = check_citation_coverage(answer, sources)
    assert not has_coverage
    assert any("non-existent" in w.lower() for w in warnings)
