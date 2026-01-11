"""
RAG Pipeline with Qdrant Vector Database

A complete Retrieval-Augmented Generation pipeline featuring:
- Document chunking and indexing
- Semantic search with MMR (Maximal Marginal Relevance)
- Cross-encoder reranking
- Deduplication strategies
- LLM integration (vLLM, Ollama, or Mistral API)
- Evaluation metrics (recall@k, nDCG@k, latency, groundedness)

Author: Senior AI Engineer
"""

import sys
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder
from dotenv import load_dotenv
import os

# Import modules
from config import DOCS, EMBED_MODEL, RERANK_MODEL
from document_processing import build_corpus
from indexing import ensure_collection, index
from retrieval import search
from prompting import build_prompt
from utils.metrics_relevance import eval_query
from utils.latency_utils import measure_latency
from utils.groundedness_proxy import groundedness_proxy

# Import LLM abstraction from news_assistant
from news_assistant.llm import LLM
from news_assistant.settings import Settings

# ---------- Main ----------

def main():
    """
    Main execution function demonstrating complete RAG pipeline.
    
    Performs:
    1. Model initialization (embedding and reranking models)
    2. Qdrant client connection
    3. Corpus building and indexing
    4. Semantic search with evaluation metrics
    5. LLM response generation
    6. Groundedness validation
    
    Prints:
        - Search results with scores
        - Relevance metrics (recall@k, nDCG@k)
        - Latency metrics (p50, p95, p99)
        - Generated prompt
        - LLM response with source citations
        - Groundedness check results
    
    Environment:
        Requires LLM configuration in .env file:
        - LLM_PROVIDER: "vllm", "ollama", or "mistral"
        - For Mistral: MISTRAL_API_KEY required
        - For vLLM: VLLM_BASE_URL (default: http://localhost:8001)
        - For Ollama: OLLAMA_BASE_URL (default: http://localhost:11434)
    """
    # Load settings
    load_dotenv()
    settings = Settings()
    
    # Mallit
    model = SentenceTransformer(EMBED_MODEL)
    cross_encoder = CrossEncoder(RERANK_MODEL)  # kevyt rerankkeri
    client = QdrantClient(url="http://localhost:6333")

    # Rakennus & indeksointi
    corpus = build_corpus(DOCS)
    ensure_collection(client, dim=model.get_sentence_embedding_dimension())
    index(client, model, corpus)

    # Haku (MMR + rerank + dedupe)
    question = "Miksi vektoritietokanta on hyödyllinen RAG-järjestelmässä?"
    results = search(
        client, model, question,
        top_k=4, initial_limit=30, diversity=0.35,
        score_threshold=0.25, cross_encoder=cross_encoder
    )

    print("== Haun osumat (MMR + rerank + dedupe) ==")
    if not results:
        print("Ei riittäviä osumia (score < threshold). LLM:ää ei kutsuta.")
        print("\n== LLM-vastaus ==\n")
        print("en tiedä. Tarvitsen lisää lähteitä.")
        return
    else:
        for r in results:
            rr = r.get("rerank_score")
            rr_s = f", rerank={rr:.3f}" if rr is not None else ""
            uid_s = f", uid={r.get('uid')}" if r.get("uid") else ""
            print(f"{r['score']}{rr_s}: {r['title']} [{r['source']}] -> {r['text'][:120]}...{uid_s}")

    # == (A) Relevanssi: recall@k ja nDCG@k tälle kysymykselle ==
    gold = {d["id"] for d in DOCS}  # demossa kaikki polku/1..3 ovat “gold”
    k = len(results)

    # eval_query tarvitsee hakufunktion signatuurilla (query, top_k) -> list[dict]
    def search_fn(q, top_k):
        return search(client, model, q,
                      top_k=top_k, initial_limit=50, diversity=0.35,
                      score_threshold=0.0, cross_encoder=None)

    rel_metrics = eval_query(search_fn, question, gold, k=k)
    print("\n== Mittarit (relevanssi) ==")
    print(rel_metrics)  # sisältää preds, recall@k, ndcg@k

    # == (B) Latenssi: p50/p95/p99 pelkälle haulle (raaka nopeus, ilman rerankkausta) ==
    def run_once():
        _ = search_fn(question, top_k=4)

    lat = measure_latency(run_once, runs=20, warmup=3)
    print("\n== Latenssi (haku) ==")
    print(f"p50: {lat['p50_ms']:.1f} ms | p95: {lat['p95_ms']:.1f} ms | p99: {lat['p99_ms']:.1f} ms")

    # Prompt + LLM
    prompt = build_prompt(question, results)
    print("\n== Generointiprompt (syötä LLM:lle) ==\n")
    print(prompt)

    # Initialize LLM based on settings
    try:
        if settings.llm_provider == "mistral":
            if not settings.mistral_api_key:
                sys.exit("Missing MISTRAL_API_KEY. Set LLM_PROVIDER=vllm or LLM_PROVIDER=ollama for free options.")
            llm = LLM(
                provider="mistral",
                model=settings.mistral_model,
                api_key=settings.mistral_api_key,
            )
        elif settings.llm_provider == "vllm":
            llm = LLM(
                provider="vllm",
                model=settings.vllm_model,
                base_url=settings.vllm_base_url,
            )
        elif settings.llm_provider == "ollama":
            llm = LLM(
                provider="ollama",
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
            )
        else:
            sys.exit(f"Unknown LLM_PROVIDER: {settings.llm_provider}. Use 'vllm', 'ollama', or 'mistral'.")
    except Exception as e:
        sys.exit(f"Failed to initialize LLM: {e}")

    print(f"\n== Using LLM provider: {settings.llm_provider} ==\n")
    
    # Generate response
    try:
        out = llm.generate(prompt, max_tokens=500)
    except Exception as e:
        sys.exit(f"LLM generation failed: {e}")

    print("\n== LLM-vastaus ==\n")

    # Varmuuskatkaisin: lisää Lähteet:, jos malli unohti
    if "Lähteet:" not in out:
        used_sources = [r["source"] for r in results if r.get("source")]
        # säilytä alkuperäinen järjestys ilman duplikaatteja
        seen, ordered = set(), []
        for s in used_sources:
            if s not in seen:
                seen.add(s)
                ordered.append(s)
        src_block = "\n".join(f"- [lähde: {s}]" for s in ordered)
        out = out.rstrip() + "\n\nLähteet:\n" + src_block

    # (valinnainen pikasiivous yleisimmille sanamuodoille)
    out = out.replace("hakuun perustuva haku", "semanttinen haku")

    print(out)

    # == (C) Groundedness-proxy: löytyykö "Lähteet"-osio ja mainitaanko käytetyt lähteet ==
    used_sources = [r["source"] for r in results if r.get("source")]
    g = groundedness_proxy(out, used_sources)
    print("\n== Groundedness (proxy) ==")
    print(g)


if __name__ == "__main__":
    main()
