"""Test chunking determinism."""
from news_assistant.qdrant_store import chunk


def test_chunking_determinism():
    """Test that chunking produces stable results."""
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    
    chunks1 = chunk(text, max_len=30)
    chunks2 = chunk(text, max_len=30)
    
    assert len(chunks1) == len(chunks2)
    assert all(c1["text"] == c2["text"] for c1, c2 in zip(chunks1, chunks2))
    assert all(c1["chunk_index"] == c2["chunk_index"] for c1, c2 in zip(chunks1, chunks2))


def test_chunking_metadata():
    """Test that chunks have proper metadata."""
    text = "Sentence one. Sentence two."
    chunks = chunk(text, max_len=50)
    
    assert len(chunks) > 0
    for ch in chunks:
        assert "text" in ch
        assert "chunk_index" in ch
        assert "char_start" in ch
        assert "char_end" in ch
        assert ch["char_start"] < ch["char_end"]
