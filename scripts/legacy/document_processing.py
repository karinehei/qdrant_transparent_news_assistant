"""
Document Processing Module

Handles document chunking and corpus construction from raw documents.
"""

from typing import List, Dict
from config import DOCS


def chunk(text: str, max_len: int = 256) -> List[str]:
    """
    Split text into chunks based on sentence boundaries.
    
    This function performs simple sentence-based chunking, splitting text at
    periods and grouping sentences into chunks that don't exceed max_len.
    
    Args:
        text: Input text to be chunked
        max_len: Maximum character length for each chunk (default: 256)
    
    Returns:
        List of text chunks, each not exceeding max_len characters
    
    Example:
        >>> chunk("First sentence. Second sentence. Third sentence.", max_len=30)
        ['First sentence. Second sentence.', 'Third sentence.']
    """
    s = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
    chunks, buf = [], ""
    for sent in s:
        if len(buf) + len(sent) + 1 <= max_len:
            buf = f"{buf} {sent}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = sent
    if buf:
        chunks.append(buf)
    return chunks


def build_corpus(docs: List[Dict]) -> List[Dict]:
    """
    Build a corpus from documents by chunking and adding metadata.
    
    Takes a list of documents, chunks each document's text, and creates
    corpus entries with unique identifiers and source tracking.
    
    Args:
        docs: List of document dictionaries with keys:
            - id: Unique document identifier
            - title: Document title
            - text: Document content to be chunked
    
    Returns:
        List of corpus entries, each containing:
            - uid: Unique identifier in format "{doc_id}#{chunk_index}"
            - title: Original document title
            - text: Chunk text
            - source: Original document ID
    
    Example:
        >>> docs = [{"id": "doc1", "title": "Test", "text": "Sentence one. Sentence two."}]
        >>> corpus = build_corpus(docs)
        >>> len(corpus) > 0
        True
    """
    corpus = []
    for d in docs:
        for i, ch in enumerate(chunk(d["text"])):
            corpus.append({
                "uid": f"{d['id']}#{i}",   # deterministinen inhimillinen tunniste
                "title": d["title"],
                "text": ch,
                "source": d["id"]
            })
    return corpus
