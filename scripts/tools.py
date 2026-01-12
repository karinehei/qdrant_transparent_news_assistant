#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools.py
--------
A small, practical RAG pipeline with Qdrant. Includes:
- Collection creation and HNSW tuning (m, ef_construct, efSearch)
- Chunking and embedding computation (SentenceTransformers)
- Indexing to Qdrant with payload/metadata fields (tenant_id, doc_type, domain)
- Semantic search + ACL filters
- (Optional) CrossEncoder reranking
- (Optional) Lightweight hybrid (vector + BM25)
- Snapshot example (backup)
- Prompt builder with source references

Usage examples:
    # 1) Start Qdrant (Docker)
    # docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:latest

    # 2) Install dependencies
    # pip install qdrant-client sentence-transformers rank_bm25

    # 3) Run indexing and search
    # python tools.py --index --search "Why is vector database useful in RAG?" --print-prompt

    # 4) Hybrid and reranking
    # pip install sentence-transformers  # (already installed) + CrossEncoder uses the same package
    # python tools.py --index --search "..." --topk 8 --rerank --hybrid --print-prompt

    # 5) Snapshot
    # python tools.py --snapshot

Note: This is a demo. In production, add more error handling, logging, and more efficient corpus management.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import argparse
import uuid
import sys

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, SearchParams,
    Filter, FieldCondition, MatchValue, HnswConfigDiff
)

try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except Exception as e:
    HAS_ST = False
    SentenceTransformer = None  # type: ignore

# Reranker (optional)
try:
    from sentence_transformers import CrossEncoder
    HAS_CE = True
except Exception:
    HAS_CE = False
    CrossEncoder = None  # type: ignore

# BM25 (optional)
try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except Exception:
    HAS_BM25 = False
    BM25Okapi = None  # type: ignore


# ------------------------
# Configuration
# ------------------------
COLLECTION = "demo_docs"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ------------------------
# Example Documents
# ------------------------
DOCS: List[Dict[str, str]] = [
    {"id": "polku/1", "title": "Qdrant pähkinänkuoressa",
     "text": "Qdrant on vektoridatabäsi, joka tukee HNSW-indeksointia, metadatafilttereitä ja reaaliaikaisia päivityksiä."},
    {"id": "polku/2", "title": "RAG-perusteet",
     "text": "RAG yhdistää haun ja generoinnin: dokumentit pilkotaan, indeksoidaan vektorimuotoon ja haetaan semanttisesti."},
    {"id": "polku/3", "title": "Embeddings lyhyesti",
     "text": "Upotteet (embeddings) kuvaavat tekstin merkityssisältöä, mahdollistaen samankaltaisuushakuja kosinietäisyydellä."},
]


# ------------------------
# Helper Functions
# ------------------------
def chunk(text: str, max_len: int = 256) -> List[str]:
    """Very simple chunking with sentence delimiter."""
    s = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
    chunks, buf = [], ""
    for sent in s:
        if len(buf) + len(sent) + 1 <= max_len:
            buf = f"{buf} {sent}".strip()
        else:
            if buf: chunks.append(buf)
            buf = sent
    if buf: chunks.append(buf)
    return chunks


def build_corpus(docs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Build corpus and add metadata (tenant_id, doc_type, domain)."""
    corpus: List[Dict[str, str]] = []
    for d in docs:
        for i, ch in enumerate(chunk(d["text"])):
            corpus.append({
                "uid": f"{d['id']}#{i}",
                "title": d["title"],
                "text": ch,
                "source": d["id"],
                "domain": "demo",
                "tenant_id": "acme",        # ACL example
                "doc_type": "knowledge"     # type classification
            })
    return corpus


def ensure_collection(client: QdrantClient, dim: int) -> None:
    """Create collection with HNSW if missing (COSINE distance)."""
    exists = client.collection_exists(COLLECTION)
    if not exists:
        client.recreate_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def tune_hnsw(client: QdrantClient, m: int = 16, ef_construct: int = 256, full_scan_threshold: int = 10_000) -> None:
    """HNSW tuning for better recall."""
    client.update_collection(
        collection_name=COLLECTION,
        hnsw_config=HnswConfigDiff(
            m=m,
            ef_construct=ef_construct,
            full_scan_threshold=full_scan_threshold
        )
    )


def index_points(client: QdrantClient, model: SentenceTransformer, corpus: List[Dict[str, str]]) -> None:
    vectors = model.encode([c["text"] for c in corpus], normalize_embeddings=True).tolist()
    points = []
    for v, c in zip(vectors, corpus):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=v,
                payload={
                    "title": c["title"],
                    "text": c["text"],
                    "source": c["source"],
                    "domain": c["domain"],
                    "tenant_id": c["tenant_id"],
                    "doc_type": c["doc_type"],
                }
            )
        )
    client.upsert(collection_name=COLLECTION, points=points)


def semantic_search(
        client: QdrantClient,
        model: SentenceTransformer,
        query: str,
        top_k: int = 4,
        hnsw_ef: int = 256,
        tenant: Optional[str] = None,
        doc_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Semantic search with ACL-type filters."""
    q_vec = model.encode([query], normalize_embeddings=True).tolist()[0]
    q_filter: Optional[Filter] = None
    must = []
    if tenant:
        must.append(FieldCondition(key="tenant_id", match=MatchValue(value=tenant)))
    if doc_type:
        must.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    if must:
        q_filter = Filter(must=must)

    hits = client.search(
        collection_name=COLLECTION,
        query_vector=q_vec,
        limit=top_k,
        search_params=SearchParams(hnsw_ef=hnsw_ef),
        query_filter=q_filter
    )
    return [{
        "score": float(h.score),
        "title": h.payload.get("title"),
        "text": h.payload.get("text"),
        "source": h.payload.get("source"),
    } for h in hits]


def ensure_bm25(corpus: List[Dict[str, str]]):
    """Prepare BM25 for small demo corpus."""
    if not HAS_BM25:
        raise RuntimeError("rank_bm25 is not installed. Install: pip install rank_bm25")
    return BM25Okapi([c["text"].split() for c in corpus]), [c["text"] for c in corpus]


def hybrid_search(
        client: QdrantClient,
        model: SentenceTransformer,
        bm25: BM25Okapi,
        bm25_texts: List[str],
        question: str,
        vec_top_k: int = 20,
        final_k: int = 5,
        alpha: float = 0.6,
) -> List[Dict[str, Any]]:
    """Lightweight hybrid: combines vector and BM25 scores (weighted sum)."""
    q_vec = model.encode([question], normalize_embeddings=True).tolist()[0]
    vec_hits = client.search(
        collection_name=COLLECTION,
        query_vector=q_vec,
        limit=vec_top_k,
        search_params=SearchParams(hnsw_ef=256),
    )
    if not vec_hits:
        return []

    bm25_scores = bm25.get_scores(question.split())

    # Combine scores (min-max normalization + weighted sum)
    results = []
    for h in vec_hits:
        text = h.payload["text"]
        try:
            idx = bm25_texts.index(text)  # demo: O(n), ok for small data
        except ValueError:
            idx = -1
        v = float(h.score)
        b = float(bm25_scores[idx]) if idx >= 0 else 0.0
        results.append({"text": text, "title": h.payload["title"], "source": h.payload["source"],
                        "vec": v, "bm25": b})

    vmin, vmax = min(r["vec"] for r in results), max(r["vec"] for r in results)
    bmin, bmax = min(r["bm25"] for r in results), max(r["bm25"] for r in results)
    for r in results:
        r["vec_n"]  = 0 if vmax == vmin else (r["vec"]  - vmin)/(vmax - vmin)
        r["bm25_n"] = 0 if bmax == bmin else (r["bm25"] - bmin)/(bmax - bmin)
        r["hybrid"] = alpha*r["vec_n"] + (1 - alpha)*r["bm25_n"]

    results.sort(key=lambda x: x["hybrid"], reverse=True)
    return results[:final_k]


def ensure_reranker():
    """Create CrossEncoder reranker (optional)."""
    if not HAS_CE:
        raise RuntimeError("CrossEncoder is not available. Install: pip install sentence-transformers")
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


def rerank(question: str, results: List[Dict[str, Any]], reranker) -> List[Dict[str, Any]]:
    pairs = [(question, r["text"]) for r in results]
    scores = reranker.predict(pairs)
    for s, r in zip(scores, results):
        r["rerank"] = float(s)
    return sorted(results, key=lambda x: x["rerank"], reverse=True)


def build_prompt_with_refs(question: str, contexts: List[Dict[str, Any]]) -> str:
    lines = []
    for i, c in enumerate(contexts, 1):
        lines.append(f"[{i}] {c.get('title')} — {c.get('text')}")
    ctx = "\n\n---\n\n".join(lines)
    return f"""Answer the question using ONLY the context below. 
If the answer is not found, say 'I don't know' and ask for more sources. 
Reference sources [1], [2], ... when writing your answer.

QUESTION:
{question}

CONTEXT:
{ctx}
"""


def create_snapshot(client: QdrantClient) -> Any:
    """Create collection snapshot (file to Qdrant storage)."""
    return client.create_snapshot(collection_name=COLLECTION)


# ------------------------
# CLI
# ------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="Mini RAG Qdrant — end-to-end demo")
    ap.add_argument("--host", default="http://localhost", help="Qdrant host (default: http://localhost)")
    ap.add_argument("--port", type=int, default=6333, help="Qdrant port (default: 6333)")
    ap.add_argument("--index", action="store_true", help="Index demo documents to collection")
    ap.add_argument("--search", type=str, default=None, help="Perform search with given question")
    ap.add_argument("--topk", type=int, default=3, help="Top-K number of results (default: 3)")
    ap.add_argument("--hnsw_ef", type=int, default=256, help="Search phase hnsw_ef (default: 256)")
    ap.add_argument("--tenant", type=str, default="acme", help="ACL: tenant_id filter (default: acme)")
    ap.add_argument("--doc_type", type=str, default="knowledge", help="ACL: doc_type filter (default: knowledge)")
    ap.add_argument("--rerank", action="store_true", help="Use CrossEncoder reranking")
    ap.add_argument("--hybrid", action="store_true", help="Use lightweight hybrid (vector + BM25)")
    ap.add_argument("--snapshot", action="store_true", help="Create collection snapshot")
    ap.add_argument("--print-prompt", action="store_true", help="Print constructed prompt")
    return ap.parse_args()


def main():
    args = parse_args()

    if not HAS_ST:
        print("sentence-transformers is missing. Install: pip install sentence-transformers", file=sys.stderr)
        sys.exit(1)

    # Model and Qdrant
    model = SentenceTransformer(EMBED_MODEL)
    client = QdrantClient(url=f"{args.host}:{args.port}")

    # Collection + HNSW
    ensure_collection(client, dim=model.get_sentence_embedding_dimension())
    tune_hnsw(client)  # basic tuning

    # Build corpus
    corpus = build_corpus(DOCS)

    # Index
    if args.index:
        index_points(client, model, corpus)
        print(f"Indexed points: {len(corpus)}")

    # Snapshot
    if args.snapshot:
        snap = create_snapshot(client)
        print("Snapshot created:", snap)

    # Search
    if args.search:
        question = args.search
        results: List[Dict[str, Any]]

        if args.hybrid:
            if not HAS_BM25:
                print("Hybrid requires rank_bm25 library. Install: pip install rank_bm25", file=sys.stderr)
                sys.exit(2)
            bm25, bm25_texts = ensure_bm25(corpus)
            results = hybrid_search(client, model, bm25, bm25_texts, question, vec_top_k=max(10, args.topk*3), final_k=args.topk)
        else:
            results = semantic_search(
                client, model, question, top_k=args.topk,
                hnsw_ef=args.hnsw_ef, tenant=args.tenant, doc_type=args.doc_type
            )

        # Reranking
        if args.rerank:
            try:
                rr = ensure_reranker()
                results = rerank(question, results, rr)
                results = results[:args.topk]
            except Exception as e:
                print(f"Reranker could not be used: {e}", file=sys.stderr)

        print("== Search hits ==")
        for r in results:
            # print scores in primary sort field
            score_key = "hybrid" if "hybrid" in r else ("rerank" if "rerank" in r else "score")
            score_val = r.get(score_key, r.get("score", 0.0))
            print(f"{score_val:.3f}: {r['title']} [{r['source']}] -> {r['text'][:120]}...")

        if args.print_prompt:
            prompt = build_prompt_with_refs(question, results)
            print("\n== Generation prompt (input to LLM) ==\n")
            print(prompt)


if __name__ == "__main__":
    main()
