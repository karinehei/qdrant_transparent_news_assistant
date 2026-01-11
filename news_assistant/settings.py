from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Environment variables take precedence over .env file
    # This allows docker-compose to override .env values
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False
    )

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "news_chunks"

    # Embeddings / rerank
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    use_rerank: bool = True

    # LLM Provider (ollama, vllm, or mistral)
    llm_provider: str = "vllm"  # "ollama", "vllm", or "mistral" (default: vllm for best performance)
    
    # Ollama settings (free, local, CPU/GPU)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi:latest"  # Fast: "phi:latest" (~1.6GB), "tinyllama" (~637MB) | Quality: "mistral:latest" (~4GB), "llama2:latest" (~4-7GB)
    
    # vLLM settings (fast, GPU-optimized, OpenAI-compatible API)
    vllm_base_url: str = "http://localhost:8001"  # Default vLLM port (8001 to avoid conflict with API on 8000)
    vllm_model: str = "microsoft/Phi-3-mini-4k-instruct"  # Or any HuggingFace model
    
    # Mistral settings (requires API key)
    mistral_api_key: str | None = None
    mistral_model: str = "mistral-small-latest"

    # Audit DB (PostgreSQL in production, SQLite for dev)
    audit_db_url: str = "postgresql://news_user:news_pass@localhost:5432/news_audit"

    # Retrieval
    top_k: int = 12
    mmr_k: int = 6
    score_threshold: float = 0.25
    use_bm25: bool = False  # Enable hybrid search
    bm25_weight: float = 0.3  # Weight for BM25 in hybrid search
    
    # Relevance Quality Control
    relevance_threshold: float = 0.25  # Minimum relevance score to answer (0.0-1.0) - lowered for better recall
    min_relevant_sources: int = 1  # Minimum number of sources above relevance threshold
    use_relevance_gate: bool = True  # Enable strict relevance checking
    
    # Topic-based retrieval
    topic_retrieval_candidates: int = 50  # Fetch more candidates for topic filtering
    topic_min_sources: int = 2  # Minimum sources required for topic queries
    topic_relevance_threshold: float = 0.30  # Threshold for topic relevance filtering

    # Safety
    max_answer_tokens: int = 400  # Increased for more complete responses


settings = Settings()
