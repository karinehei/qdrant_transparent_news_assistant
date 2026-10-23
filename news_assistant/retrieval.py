"""Enhanced retrieval with hybrid search (vector + BM25)."""

from __future__ import annotations

import logging

import numpy as np
from qdrant_client import QdrantClient
from sentence_transformers import CrossEncoder, SentenceTransformer

logger = logging.getLogger(__name__)

# Try to import BM25, but make it optional
try:
    from rank_bm25 import BM25Okapi

    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger.warning("rank-bm25 not available. BM25 search will be disabled.")


def _normalize_vector(x: np.ndarray) -> np.ndarray:
    """Normalize vector to unit length."""
    n = np.linalg.norm(x)
    return x if n == 0 else x / n


def _mmr_select(
    query_vec: np.ndarray,
    doc_vecs: list[np.ndarray],
    top_n: int = 6,
    lambda_param: float = 0.6,
) -> list[int]:
    """
    Maximal Marginal Relevance selection.

    Args:
        query_vec: Query embedding vector
        doc_vecs: List of document embedding vectors
        top_n: Number of documents to select
        lambda_param: Balance between relevance (1.0) and diversity (0.0)

    Returns:
        List of indices into doc_vecs
    """
    # Check if doc_vecs is empty (handle numpy array properly)
    # embed_model.encode() returns a 2D numpy array, not a list
    if isinstance(doc_vecs, np.ndarray):
        if doc_vecs.shape[0] == 0:
            return []
        # Convert 2D array to list of 1D vectors
        dv = [_normalize_vector(v.astype(np.float32)) for v in doc_vecs]
    else:
        # Handle list case (shouldn't happen with current code, but be safe)
        if len(doc_vecs) == 0:
            return []
        dv = [_normalize_vector(v.astype(np.float32)) for v in doc_vecs]

    q = _normalize_vector(query_vec.astype(np.float32))

    # Similarities to query
    sims_to_q = [float(np.dot(q, v)) for v in dv]

    # Start with most relevant
    selected = [int(np.argmax(sims_to_q))]
    candidates = [i for i in range(len(dv)) if i != selected[0]]

    # Greedily add documents that balance relevance and diversity
    while len(selected) < min(top_n, len(dv)) and candidates:
        best_idx = None
        best_score = -1e9

        for i in candidates:
            # Relevance to query
            relevance = sims_to_q[i]

            # Max similarity to already selected
            max_sim_to_selected = max(float(np.dot(dv[i], dv[j])) for j in selected)

            # MMR score: balance relevance and diversity
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        if best_idx is not None:
            selected.append(best_idx)
            candidates.remove(best_idx)
        else:
            break

    return selected


def _bm25_search(
    query: str,
    documents: list[str],
    doc_indices: list[int],
    top_k: int = 10,
) -> list[dict[str, any]]:
    """
    BM25 keyword search.

    Args:
        query: Search query
        documents: List of document texts
        doc_indices: Original indices of documents
        top_k: Number of results to return

    Returns:
        List of dicts with keys: index, score
    """
    if not BM25_AVAILABLE or not documents:
        return []

    try:
        # Tokenize (simple whitespace split)
        tokenized_docs = [doc.lower().split() for doc in documents]
        tokenized_query = query.lower().split()

        if not tokenized_query:
            return []

        bm25 = BM25Okapi(tokenized_docs)
        scores = bm25.get_scores(tokenized_query)

        # Get top-k
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only return positive scores
                results.append(
                    {
                        "index": doc_indices[idx],
                        "score": float(scores[idx]),
                    }
                )

        return results
    except Exception:
        logger.exception("BM25 search error")
        return []


def hybrid_search(
    client: QdrantClient,
    collection: str,
    embed_model: SentenceTransformer,
    query: str,
    top_k: int = 12,
    mmr_k: int = 6,
    score_threshold: float = 0.25,
    use_bm25: bool = False,
    bm25_weight: float = 0.3,
    rerank_model: CrossEncoder | None = None,
) -> list[dict]:
    """
    Hybrid search combining vector search with optional BM25.

    Args:
        client: Qdrant client
        collection: Collection name
        embed_model: Embedding model
        query: Search query
        top_k: Final number of results
        mmr_k: Number of results for MMR selection
        score_threshold: Minimum vector similarity score
        use_bm25: Whether to use BM25 keyword search
        bm25_weight: Weight for BM25 scores (0.0-1.0)
        rerank_model: Optional cross-encoder for reranking

    Returns:
        List of search hits with scores and metadata
    """
    # Vector search - use query_points API (newer Qdrant client)
    query_vec = embed_model.encode([query], normalize_embeddings=True)[0]
    query_vec_list = query_vec.tolist()

    # Retrieve more candidates for hybrid fusion
    initial_limit = top_k * 3 if use_bm25 else top_k

    # Use query_points API (newer Qdrant client)
    # Pass vector list directly - Qdrant client accepts list as query
    query_result = client.query_points(
        collection_name=collection,
        query=query_vec_list,  # Direct list works
        limit=initial_limit,
        with_payload=True,
        with_vectors=False,  # We don't need vectors for BM25
    )
    vector_results = query_result.points

    # Filter by threshold and convert to dicts
    hits = []
    for r in vector_results:
        if r.score is None or r.score < score_threshold:
            continue
        hits.append(
            {
                "id": str(r.id),
                "score": float(r.score),
                "payload": r.payload or {},
            }
        )

    if not hits:
        return []

    # Hybrid fusion: combine vector and BM25 scores
    if use_bm25 and BM25_AVAILABLE and len(hits) > 1:
        documents = [h["payload"].get("text", "") for h in hits]
        doc_indices = list(range(len(hits)))

        bm25_results = _bm25_search(query, documents, doc_indices, top_k=len(hits))

        # Normalize BM25 scores (simple min-max)
        if bm25_results:
            bm25_scores = [r["score"] for r in bm25_results]
            if max(bm25_scores) > min(bm25_scores):
                bm25_max = max(bm25_scores)
                bm25_min = min(bm25_scores)
                bm25_normalized = {r["index"]: (r["score"] - bm25_min) / (bm25_max - bm25_min) for r in bm25_results}
            else:
                bm25_normalized = {r["index"]: 1.0 for r in bm25_results}

            # Normalize vector scores (they're already 0-1 from cosine similarity)
            vector_scores = [h["score"] for h in hits]
            vector_max = max(vector_scores) if vector_scores else 1.0
            vector_min = min(vector_scores) if vector_scores else 0.0
            if vector_max > vector_min:
                vector_normalized = {i: (h["score"] - vector_min) / (vector_max - vector_min) for i, h in enumerate(hits)}
            else:
                vector_normalized = {i: 1.0 for i in range(len(hits))}

            # Combine scores
            for i, h in enumerate(hits):
                vector_score = vector_normalized.get(i, 0.0)
                bm25_score = bm25_normalized.get(i, 0.0)
                # Weighted combination
                combined_score = (1 - bm25_weight) * vector_score + bm25_weight * bm25_score
                h["hybrid_score"] = combined_score
                h["bm25_score"] = bm25_score

            # Sort by hybrid score
            hits.sort(key=lambda x: x.get("hybrid_score", x["score"]), reverse=True)
        else:
            # No BM25 results, use vector scores
            for h in hits:
                h["hybrid_score"] = h["score"]

    # MMR selection if we have enough hits
    if len(hits) > mmr_k:
        # Get document vectors for MMR (need to fetch them)
        doc_texts = [h["payload"].get("text", "") for h in hits[: mmr_k * 2]]
        if doc_texts:
            doc_vecs = embed_model.encode(doc_texts, normalize_embeddings=True)
            query_vec_np = np.array(query_vec)

            # Select diverse subset
            selected_indices = _mmr_select(query_vec_np, doc_vecs, top_n=mmr_k)
            selected_hits = [hits[i] for i in selected_indices if i < len(hits)]
        else:
            selected_hits = hits[:mmr_k]
    else:
        selected_hits = hits

    # Reranking
    if rerank_model is not None and selected_hits:
        pairs = [(query, h["payload"].get("text", "")) for h in selected_hits]
        rerank_scores = rerank_model.predict(pairs)

        for h, score in zip(selected_hits, rerank_scores):
            h["rerank_score"] = float(score)

        # Sort by rerank score
        selected_hits.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)

    # Return top_k
    return selected_hits[:top_k]
