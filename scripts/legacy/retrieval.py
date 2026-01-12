"""
Retrieval Module

Handles semantic search, MMR selection, reranking, and deduplication.
"""

from typing import List, Dict, Tuple, Optional
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np
from config import COLLECTION, DEDUPE_BY_SOURCE


def _nz_norm(x: np.ndarray) -> np.ndarray:
    """
    Normalize vector to unit length (L2 norm) with numerical stability.
    
    Args:
        x: Input vector as numpy array
    
    Returns:
        Normalized vector (unit length)
    
    Note:
        Adds small epsilon (1e-12) to prevent division by zero.
    """
    n = np.linalg.norm(x)
    return x / (n + 1e-12)


def _dedupe_by_uid(items: List[Dict]) -> List[Dict]:
    """
    Remove duplicate items based on UID, with fallback to (source, text) tuple.
    
    Args:
        items: List of dictionaries potentially containing duplicates
    
    Returns:
        List of unique items, preserving first occurrence of each UID
    
    Note:
        Falls back to (source, text) tuple if UID is not present.
    """
    unique, seen = [], set()
    for it in items:
        key = it.get("uid") or (it.get("source", ""), it.get("text", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return unique


def _dedupe_by_source(items: List[Dict]) -> List[Dict]:
    """
    Keep at most one chunk per source document.
    
    Args:
        items: List of dictionaries with 'source' key
    
    Returns:
        List with maximum one item per unique source value
    
    Note:
        Useful for ensuring diversity across different source documents
        rather than multiple chunks from the same source.
    """
    unique, seen = [], set()
    for it in items:
        src = it.get("source")
        if src in seen:
            continue
        seen.add(src)
        unique.append(it)
    return unique


def mmr_select(query_vec: np.ndarray, doc_vecs: List[np.ndarray], top_n: int, diversity: float = 0.35) -> List[int]:
    """
    Select documents using Maximal Marginal Relevance (MMR) algorithm.
    
    MMR balances relevance to the query with diversity among selected documents.
    It iteratively selects documents that maximize: (1-λ) * relevance - λ * max_similarity_to_selected
    
    Args:
        query_vec: Query embedding vector (normalized)
        doc_vecs: List of document embedding vectors (will be normalized)
        top_n: Number of documents to select
        diversity: Diversity parameter in [0, 1]:
                   - 0.0: Pure relevance (no diversity consideration)
                   - 1.0: Maximum diversity (minimize similarity to selected)
                   - 0.35: Balanced default (moderate diversity)
    
    Returns:
        List of indices into doc_vecs representing selected documents
    
    Algorithm:
        1. Select most relevant document first
        2. For each remaining position:
           - Score each candidate: (1-λ) * sim(query, doc) - λ * max(sim(doc, selected))
           - Select candidate with highest score
        3. Repeat until top_n documents selected
    
    Example:
        >>> query = np.array([1, 0, 0])
        >>> docs = [np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1])]
        >>> selected = mmr_select(query, docs, top_n=2, diversity=0.5)
        >>> len(selected) == 2
        True
    
    Reference:
        Carbonell, J. & Goldstein, J. (1998). The Use of MMR, Diversity-Based
        Reranking for Reordering Documents and Producing Summaries.
    """
    if not doc_vecs:
        return []
    q = _nz_norm(query_vec.astype(np.float32))
    dv = [_nz_norm(v.astype(np.float32)) for v in doc_vecs]

    sims_to_q = [float(np.dot(q, v)) for v in dv]
    selected = [int(np.argmax(sims_to_q))]
    candidates = [i for i in range(len(dv)) if i != selected[0]]

    while len(selected) < min(top_n, len(dv)) and candidates:
        best, best_val = None, -1e-9
        for c in candidates:
            relevance = sims_to_q[c]
            diversity_penalty = max(float(np.dot(dv[c], dv[s])) for s in selected)
            score = (1 - diversity) * relevance - diversity * diversity_penalty
            if score > best_val:
                best, best_val = c, score
        selected.append(best)
        candidates.remove(best)
    return selected


def crossencode_rerank(cross_encoder: CrossEncoder, query: str, items: List[Dict], top_k: int) -> List[Dict]:
    """
    Rerank items using a cross-encoder model.
    
    Cross-encoders provide more accurate relevance scores than bi-encoders
    by jointly encoding query-document pairs, at the cost of higher latency.
    
    Args:
        cross_encoder: CrossEncoder model instance
        query: Search query string
        items: List of candidate items with 'text' key
        top_k: Number of top items to return after reranking
    
    Returns:
        Top-k items sorted by rerank_score (descending), with added 'rerank_score' field
    
    Note:
        Modifies items in-place by adding 'rerank_score' field.
    """
    pairs = [(query, it["text"]) for it in items]
    scores = cross_encoder.predict(pairs).tolist()
    for it, sc in zip(items, scores):
        it["rerank_score"] = float(sc)
    items.sort(key=lambda x: x["rerank_score"], reverse=True)
    return items[:top_k]


def search(
    client: QdrantClient,
    model: SentenceTransformer,
    query: str,
    top_k: int = 4,
    initial_limit: int = 30,   # enemmän kandidaatteja MMR:lle
    diversity: float = 0.35,   # maltillinen
    score_threshold: float = 0.25,
    cross_encoder: Optional[CrossEncoder] = None,
) -> List[Dict]:
    """
    Perform semantic search with MMR, optional reranking, and deduplication.
    
    Pipeline:
    1. Vector search in Qdrant (retrieves initial_limit candidates)
    2. Filter by score_threshold
    3. Apply MMR for diversity (selects top_k * 2 candidates)
    4. Optional cross-encoder reranking
    5. Deduplication (by UID or source based on DEDUPE_BY_SOURCE flag)
    6. Return top_k final results
    
    Args:
        client: QdrantClient instance
        model: SentenceTransformer for query embedding
        query: Search query string
        top_k: Final number of results to return
        initial_limit: Number of candidates to retrieve from Qdrant (before MMR)
        diversity: MMR diversity parameter (0.0 = pure relevance, 1.0 = max diversity)
        score_threshold: Minimum similarity score to include (0.0-1.0)
        cross_encoder: Optional CrossEncoder for reranking
    
    Returns:
        List of search results, each containing:
            - uid: Unique identifier
            - score: Vector similarity score
            - rerank_score: Optional reranking score (if reranker used)
            - title: Document title
            - text: Chunk text
            - source: Source document ID
    
    Example:
        >>> results = search(client, model, "vector database", top_k=5)
        >>> len(results) <= 5
        True
    """
    # 1) Ensihaku Qdrantista (pyydä vektorit & payloadit takaisin)
    q_vec = model.encode([query], normalize_embeddings=True)[0]
    hits = client.search(
        collection_name=COLLECTION,
        query_vector=q_vec.tolist(),
        limit=initial_limit,
        with_vectors=True,
        with_payload=True,
    )

    # Suodata heikot osumat (vector-score)
    prelim = [h for h in hits if (h.score is None or h.score >= score_threshold)]
    if not prelim:
        return []  # -> ei kontekstia; main() ei kutsu LLM:ää

    # 2) Kerää vektorit ja aja MMR
    prelim_with_vecs: List[Tuple[np.ndarray, object]] = []
    for h in prelim:
        if getattr(h, "vector", None) is not None:
            prelim_with_vecs.append((np.array(h.vector, dtype=np.float32), h))
    if not prelim_with_vecs:
        return []

    idxs = mmr_select(np.array(q_vec), [v for v, _ in prelim_with_vecs],
                      top_n=min(top_k * 2, len(prelim_with_vecs)), diversity=diversity)
    mmr_hits = [prelim_with_vecs[i][1] for i in idxs]

    # 3) Muodosta dictit (sis. uid)
    mmr_items = [{
        "uid": h.payload.get("uid"),
        "score": round(h.score, 3) if h.score is not None else None,
        "title": h.payload.get("title"),
        "text": h.payload.get("text"),
        "source": h.payload.get("source"),
    } for h in mmr_hits]

    # 4) Rerank (valinnainen)
    if cross_encoder is not None and len(mmr_items) > 1:
        mmr_items = crossencode_rerank(cross_encoder, query, mmr_items, top_k=max(top_k, 2))

    # 5) Deduplikointi
    if DEDUPE_BY_SOURCE:
        unique = _dedupe_by_source(mmr_items)
    else:
        unique = _dedupe_by_uid(mmr_items)

    return unique[:top_k]
