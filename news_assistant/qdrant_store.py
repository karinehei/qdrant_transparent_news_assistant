from __future__ import annotations
from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder

from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

import numpy as np


def ensure_collection(client: QdrantClient, collection: str, dim: int):
    try:
        client.get_collection(collection)
    except Exception:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def chunk(text: str, max_len: int = 300) -> List[Dict[str, any]]:
    """
    Stable sentence-based chunking with metadata.

    Returns list of dicts with keys: text, chunk_index, char_start, char_end
    """
    # Normalize whitespace but preserve structure
    text = " ".join(text.split())
    sents = [s.strip() + "." for s in text.split(".") if s.strip()]

    chunks = []
    cur = ""
    char_pos = 0

    for sent in sents:
        cand = (cur + " " + sent).strip() if cur else sent
        if len(cand) <= max_len:
            cur = cand
        else:
            if cur:
                chunk_start = char_pos - len(cur)
                chunks.append(
                    {
                        "text": cur,
                        "chunk_index": len(chunks),
                        "char_start": max(0, chunk_start),
                        "char_end": char_pos,
                    }
                )
            cur = sent
        char_pos += len(sent) + 1  # +1 for space/separator

    if cur:
        chunk_start = char_pos - len(cur)
        chunks.append(
            {
                "text": cur,
                "chunk_index": len(chunks),
                "char_start": max(0, chunk_start),
                "char_end": char_pos,
            }
        )

    return chunks


def build_corpus_from_articles(articles: List[Dict]) -> List[Dict]:
    """
    Build corpus from articles with stable chunk IDs and metadata.

    Each chunk gets a deterministic UID based on (url + published_at + chunk_index).
    """
    corpus = []
    for a in articles:
        source_id = a.get("id") or a.get("url") or a.get("source_id") or "unknown"
        url = a.get("url", "")
        published_at = a.get("published_at", "")

        # Use stable chunking
        chunk_data = chunk(a.get("text", ""))

        for ch_info in chunk_data:
            chunk_index = ch_info["chunk_index"]
            # Deterministic UID: hash of (url + published_at + chunk_index)
            # This ensures same article+chunk always gets same UID
            chunk_uid = f"{source_id}#{chunk_index}"

            corpus.append(
                {
                    "uid": chunk_uid,
                    "title": a.get("title", ""),
                    "text": ch_info["text"],
                    "source_id": source_id,
                    "article_id": source_id,  # Alias for clarity
                    "url": url,
                    "published_at": published_at,
                    "publisher": a.get("publisher"),
                    "chunk_index": chunk_index,
                    "char_start": ch_info["char_start"],
                    "char_end": ch_info["char_end"],
                }
            )
    return corpus


def index_articles(
    client: QdrantClient,
    collection: str,
    embed_model: SentenceTransformer,
    articles: List[Dict],
    incremental: bool = True,
) -> int:
    """
    Index articles into Qdrant with incremental re-index support.

    Args:
        client: Qdrant client
        collection: Collection name
        embed_model: Embedding model
        articles: List of article dicts
        incremental: If True, uses deterministic IDs to avoid duplicates

    Returns:
        Number of chunks indexed
    """
    corpus = build_corpus_from_articles(articles)
    if not corpus:
        return 0

    vecs = embed_model.encode([c["text"] for c in corpus], normalize_embeddings=True).tolist()
    points = []

    for v, c in zip(vecs, corpus):
        # Deterministic point ID: hash of (url + published_at + chunk_index)
        # This ensures same chunk always gets same point ID, enabling idempotent indexing
        if incremental:
            # Use deterministic UUID based on stable UID
            pid = uuid.uuid5(uuid.NAMESPACE_URL, c["uid"])
        else:
            # Generate new UUID for each indexing run
            pid = uuid.uuid4()

        payload = dict(c)
        points.append(PointStruct(id=str(pid), vector=v, payload=payload))

    if points:
        client.upsert(collection_name=collection, points=points)

    return len(points)


def delete_article_by_url(
    client: QdrantClient,
    collection: str,
    url: str,
) -> int:
    """
    Delete all chunks for an article by URL.

    Args:
        client: Qdrant client
        collection: Collection name
        url: Article URL

    Returns:
        Number of points deleted
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    # Search for all points with this URL
    filter_condition = Filter(must=[FieldCondition(key="url", match=MatchValue(value=url))])

    # Get all matching point IDs
    scroll_result = client.scroll(
        collection_name=collection,
        scroll_filter=filter_condition,
        limit=10000,  # Adjust if needed
        with_payload=False,
        with_vectors=False,
    )

    point_ids = [point.id for point in scroll_result[0]]

    if point_ids:
        client.delete(collection_name=collection, points_selector=point_ids)

    return len(point_ids)


def delete_article_by_id(
    client: QdrantClient,
    collection: str,
    article_id: str,
) -> int:
    """
    Delete all chunks for an article by article_id/source_id.

    Args:
        client: Qdrant client
        collection: Collection name
        article_id: Article ID (source_id)

    Returns:
        Number of points deleted
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    filter_condition = Filter(must=[FieldCondition(key="article_id", match=MatchValue(value=article_id))])

    scroll_result = client.scroll(
        collection_name=collection,
        scroll_filter=filter_condition,
        limit=10000,
        with_payload=False,
        with_vectors=False,
    )

    point_ids = [point.id for point in scroll_result[0]]

    if point_ids:
        client.delete(collection_name=collection, points_selector=point_ids)

    return len(point_ids)


def _nz_norm(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x)
    return x if n == 0 else x / n


def mmr_select(query_vec: np.ndarray, doc_vecs: List[np.ndarray], top_n: int = 6, lam: float = 0.6) -> List[int]:
    if not doc_vecs:
        return []
    q = _nz_norm(query_vec.astype(np.float32))
    dv = [_nz_norm(v.astype(np.float32)) for v in doc_vecs]
    sims_to_q = [float(np.dot(q, v)) for v in dv]
    selected = [int(np.argmax(sims_to_q))]
    candidates = [i for i in range(len(dv)) if i != selected[0]]
    while len(selected) < min(top_n, len(dv)) and candidates:
        best, best_val = None, -1e9
        for i in candidates:
            div = max(float(np.dot(dv[i], dv[j])) for j in selected)
            val = lam * sims_to_q[i] - (1 - lam) * div
            if val > best_val:
                best, best_val = i, val
        selected.append(best)  # type: ignore
        candidates.remove(best)  # type: ignore
    return selected


def search(
    client: QdrantClient,
    collection: str,
    embed_model: SentenceTransformer,
    rerank_model: Optional[CrossEncoder],
    query: str,
    top_k: int = 12,
    mmr_k: int = 6,
    score_threshold: float = 0.25,
) -> List[Dict]:
    qv = embed_model.encode([query], normalize_embeddings=True)[0].tolist()
    # Use query_points API (newer Qdrant client)
    # Pass vector list directly - Qdrant client accepts list as query
    query_result = client.query_points(
        collection_name=collection,
        query=qv,  # Direct list works
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )
    res = query_result.points
    hits = []
    for r in res:
        if r.score is None or r.score < score_threshold:
            continue
        hits.append(
            {
                "id": str(r.id),
                "score": float(r.score),
                "payload": r.payload or {},
                "vector": None,
            }
        )
    if not hits:
        return []

    # MMR selection on payload vectors? We didn't fetch vectors; keep simple by selecting top by score then rerank.
    selected = hits[:mmr_k]

    if rerank_model is not None:
        pairs = [(query, h["payload"].get("text", "")) for h in selected]
        scores = rerank_model.predict(pairs)
        for h, s in zip(selected, scores):
            h["rerank_score"] = float(s)
        selected.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)

    return selected
