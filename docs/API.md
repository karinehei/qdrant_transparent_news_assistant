# API Reference Documentation

Complete API reference for the Qdrant RAG Pipeline project.

## Table of Contents

- [Main Pipeline (`mini_rag_pipeline_qdrant.py`)](#main-pipeline)
- [CLI Tool (`tools.py`)](#cli-tool)
- [Utility Modules](#utility-modules)

---

## Main Pipeline

### `mini_rag_pipeline_qdrant.py`

#### Document Processing

##### `chunk(text: str, max_len: int = 256) -> List[str]`

Split text into chunks based on sentence boundaries.

**Parameters:**
- `text` (str): Input text to be chunked
- `max_len` (int, optional): Maximum character length for each chunk. Default: 256

**Returns:**
- `List[str]`: List of text chunks, each not exceeding max_len characters

**Example:**
```python
chunks = chunk("First sentence. Second sentence. Third sentence.", max_len=30)
# Returns: ['First sentence. Second sentence.', 'Third sentence.']
```

---

##### `build_corpus(docs: List[Dict]) -> List[Dict]`

Build a corpus from documents by chunking and adding metadata.

**Parameters:**
- `docs` (List[Dict]): List of document dictionaries with keys:
  - `id` (str): Unique document identifier
  - `title` (str): Document title
  - `text` (str): Document content to be chunked

**Returns:**
- `List[Dict]`: List of corpus entries, each containing:
  - `uid` (str): Unique identifier in format "{doc_id}#{chunk_index}"
  - `title` (str): Original document title
  - `text` (str): Chunk text
  - `source` (str): Original document ID

**Example:**
```python
docs = [
    {"id": "doc1", "title": "Test", "text": "Sentence one. Sentence two."}
]
corpus = build_corpus(docs)
# Returns: [
#     {"uid": "doc1#0", "title": "Test", "text": "Sentence one.", "source": "doc1"},
#     {"uid": "doc1#1", "title": "Test", "text": "Sentence two.", "source": "doc1"}
# ]
```

---

#### Indexing

##### `ensure_collection(client: QdrantClient, dim: int) -> None`

Ensure Qdrant collection exists, creating it if necessary.

**Parameters:**
- `client` (QdrantClient): QdrantClient instance connected to Qdrant server
- `dim` (int): Vector dimension size (must match embedding model output)

**Note:**
- If `RESET` flag is True, deletes existing collection before creating
- Collection uses COSINE distance metric for vector similarity
- Set `RESET=True` to delete and recreate collection. Set to False after first run to preserve existing data

---

##### `index(client: QdrantClient, model: SentenceTransformer, corpus: List[Dict]) -> None`

Index corpus into Qdrant collection.

**Parameters:**
- `client` (QdrantClient): QdrantClient instance
- `model` (SentenceTransformer): SentenceTransformer model for generating embeddings
- `corpus` (List[Dict]): List of corpus entries with 'text', 'uid', 'title', 'source' keys

**Note:**
- Uses uuid5 with NAMESPACE_URL to generate deterministic UUIDs from UIDs
- This ensures same UID always maps to same UUID, enabling idempotent indexing
- Embeddings are normalized before storage

---

#### Search and Retrieval

##### `mmr_select(query_vec: np.ndarray, doc_vecs: List[np.ndarray], top_n: int, diversity: float = 0.35) -> List[int]`

Select documents using Maximal Marginal Relevance (MMR) algorithm.

**Parameters:**
- `query_vec` (np.ndarray): Query embedding vector (normalized)
- `doc_vecs` (List[np.ndarray]): List of document embedding vectors (will be normalized)
- `top_n` (int): Number of documents to select
- `diversity` (float, optional): Diversity parameter in [0, 1]:
  - `0.0`: Pure relevance (no diversity consideration)
  - `1.0`: Maximum diversity (minimize similarity to selected)
  - `0.35`: Balanced default (moderate diversity)

**Returns:**
- `List[int]`: List of indices into doc_vecs representing selected documents

**Algorithm:**
1. Select most relevant document first
2. For each remaining position:
   - Score each candidate: `(1-λ) * sim(query, doc) - λ * max(sim(doc, selected))`
   - Select candidate with highest score
3. Repeat until top_n documents selected

---

##### `crossencode_rerank(cross_encoder: CrossEncoder, query: str, items: List[Dict], top_k: int) -> List[Dict]`

Rerank items using a cross-encoder model.

**Parameters:**
- `cross_encoder` (CrossEncoder): CrossEncoder model instance
- `query` (str): Search query string
- `items` (List[Dict]): List of candidate items with 'text' key
- `top_k` (int): Number of top items to return after reranking

**Returns:**
- `List[Dict]`: Top-k items sorted by rerank_score (descending), with added 'rerank_score' field

**Note:**
- Modifies items in-place by adding 'rerank_score' field
- Cross-encoders provide more accurate relevance scores than bi-encoders by jointly encoding query-document pairs
- Higher latency than bi-encoder search but better accuracy

---

##### `search(client: QdrantClient, model: SentenceTransformer, query: str, top_k: int = 4, initial_limit: int = 30, diversity: float = 0.35, score_threshold: float = 0.25, cross_encoder: Optional[CrossEncoder] = None) -> List[Dict]`

Perform semantic search with MMR, optional reranking, and deduplication.

**Parameters:**
- `client` (QdrantClient): QdrantClient instance
- `model` (SentenceTransformer): SentenceTransformer for query embedding
- `query` (str): Search query string
- `top_k` (int, optional): Final number of results to return. Default: 4
- `initial_limit` (int, optional): Number of candidates to retrieve from Qdrant (before MMR). Default: 30
- `diversity` (float, optional): MMR diversity parameter (0.0 = pure relevance, 1.0 = max diversity). Default: 0.35
- `score_threshold` (float, optional): Minimum similarity score to include (0.0-1.0). Default: 0.25
- `cross_encoder` (Optional[CrossEncoder], optional): Optional CrossEncoder for reranking. Default: None

**Returns:**
- `List[Dict]`: List of search results, each containing:
  - `uid` (str): Unique identifier
  - `score` (float): Vector similarity score
  - `rerank_score` (float, optional): Reranking score (if reranker used)
  - `title` (str): Document title
  - `text` (str): Chunk text
  - `source` (str): Source document ID

**Pipeline:**
1. Vector search in Qdrant (retrieves initial_limit candidates)
2. Filter by score_threshold
3. Apply MMR for diversity (selects top_k * 2 candidates)
4. Optional cross-encoder reranking
5. Deduplication (by UID or source based on DEDUPE_BY_SOURCE flag)
6. Return top_k final results

**Example:**
```python
results = search(
    client, model, "vector database",
    top_k=5, diversity=0.4, cross_encoder=reranker
)
# Returns list of 5 results with scores and metadata
```

---

#### Prompt Construction

##### `format_contexts(contexts: List[Dict]) -> str`

Format retrieved contexts into a readable string for prompt construction.

**Parameters:**
- `contexts` (List[Dict]): List of context dictionaries with 'source', 'title', 'text', 'score'

**Returns:**
- `str`: Formatted string with contexts separated by delimiters, or empty string if no contexts

---

##### `build_prompt(question: str, contexts: List[Dict]) -> str`

Build a prompt for LLM with question and retrieved contexts.

**Parameters:**
- `question` (str): User's question
- `contexts` (List[Dict]): List of retrieved context dictionaries

**Returns:**
- `str`: Complete prompt string ready for LLM input

**Note:**
- Prompt is optimized for Finnish language responses
- Instructs LLM to use only provided context and include source citations
- Modify for other languages as needed

---

#### Main Function

##### `main() -> None`

Main execution function demonstrating complete RAG pipeline.

**Performs:**
1. Model initialization (embedding and reranking models)
2. Qdrant client connection
3. Corpus building and indexing
4. Semantic search with evaluation metrics
5. LLM response generation
6. Groundedness validation

**Prints:**
- Search results with scores
- Relevance metrics (recall@k, nDCG@k)
- Latency metrics (p50, p95, p99)
- Generated prompt
- LLM response with source citations
- Groundedness check results

**Environment:**
- Requires `MISTRAL_API_KEY` environment variable or `.env` file

---

## CLI Tool

### `tools.py`

Command-line interface for RAG operations with additional features like hybrid search and HNSW tuning.

#### Command-Line Arguments

```bash
python tools.py [OPTIONS]
```

**Options:**
- `--host` (str): Qdrant host (default: http://localhost)
- `--port` (int): Qdrant port (default: 6333)
- `--index`: Index demo documents to collection
- `--search` (str): Perform search with given query
- `--topk` (int): Number of results to return (default: 3)
- `--hnsw_ef` (int): HNSW ef parameter for search (default: 256)
- `--tenant` (str): ACL filter: tenant_id (default: acme)
- `--doc_type` (str): ACL filter: doc_type (default: knowledge)
- `--rerank`: Use CrossEncoder reranking
- `--hybrid`: Use hybrid search (vector + BM25)
- `--snapshot`: Create collection snapshot
- `--print-prompt`: Print generated prompt

**Examples:**
```bash
# Basic indexing and search
python tools.py --index --search "Why use vector databases?"

# With reranking
python tools.py --search "..." --rerank --topk 5

# Hybrid search
python tools.py --search "..." --hybrid --topk 8

# With ACL filters
python tools.py --search "..." --tenant acme --doc_type knowledge
```

---

## Utility Modules

### `utils/metrics_relevance.py`

#### `dcg(relevances: List[float], k: int) -> float`

Calculate Discounted Cumulative Gain (DCG).

**Parameters:**
- `relevances` (List[float]): List of relevance scores (typically 0 or 1 for binary relevance)
- `k` (int): Number of top positions to consider

**Returns:**
- `float`: DCG score (higher is better)

**Formula:**
```
DCG@k = sum(rel[i] / log2(i + 2)) for i in [0, k)
```

---

#### `ndcg_at_k(relevances: List[float], k: int) -> float`

Calculate Normalized Discounted Cumulative Gain at position k.

**Parameters:**
- `relevances` (List[float]): List of relevance scores for items in ranked order
- `k` (int): Number of top positions to consider

**Returns:**
- `float`: nDCG@k score (0.0 to 1.0, where 1.0 is perfect ranking)

---

#### `recall_at_k(relevances: List[int], k: int) -> float`

Calculate Recall at position k.

**Parameters:**
- `relevances` (List[int]): List of binary relevance labels (0 or 1) for ranked items
- `k` (int): Number of top positions to consider

**Returns:**
- `float`: Recall@k score (0.0 to 1.0, where 1.0 means all relevant items retrieved)

**Formula:**
```
Recall@k = (relevant items in top k) / (total relevant items)
```

---

#### `eval_query(search_fn: Callable[[str, int], List[Dict]], query: str, expected_sources: Iterable[str], k: int = 5) -> Dict`

Evaluate a search function on a query with expected relevant sources.

**Parameters:**
- `search_fn` (Callable): Search function that takes (query: str, top_k: int) and returns list of dicts with 'source' key
- `query` (str): Search query string
- `expected_sources` (Iterable[str]): Set or iterable of source IDs that are relevant to the query
- `k` (int, optional): Number of results to evaluate. Default: 5

**Returns:**
- `Dict`: Dictionary containing:
  - `preds` (List[str]): List of predicted source IDs from search results
  - `recall@{k}` (float): Recall at k score
  - `ndcg@{k}` (float): Normalized DCG at k score

---

### `utils/latency_utils.py`

#### `measure_latency(fn: Callable[[], None], runs: int = 30, warmup: int = 3) -> Dict[str, float]`

Measure function execution latency and compute percentile metrics.

**Parameters:**
- `fn` (Callable): Function to measure (must take no arguments)
- `runs` (int, optional): Number of measurement runs. Default: 30
- `warmup` (int, optional): Number of warmup runs to exclude from measurements. Default: 3

**Returns:**
- `Dict[str, float]`: Dictionary with latency metrics:
  - `p50_ms` (float): 50th percentile (median) latency in milliseconds
  - `p95_ms` (float): 95th percentile latency in milliseconds
  - `p99_ms` (float): 99th percentile latency in milliseconds

**Note:**
- Uses `time.perf_counter()` for high-resolution timing
- Warmup runs help account for cold-start effects (model loading, etc.)

---

### `utils/groundedness_proxy.py`

#### `groundedness_proxy(answer_text: str, allowed_sources: List[str]) -> Dict[str, bool]`

Check if LLM answer contains source citations.

**Parameters:**
- `answer_text` (str): The LLM-generated answer text
- `allowed_sources` (List[str]): List of source identifiers that should be cited

**Returns:**
- `Dict[str, bool]`: Dictionary with:
  - `has_sources_section` (bool): True if "lähteet" found in answer (case-insensitive)
  - `mentions_allowed_source` (bool): True if any allowed source is mentioned

**Note:**
- This is a simple heuristic. For production, consider using NLI models or more sophisticated fact-checking systems

---

## Configuration Constants

### `mini_rag_pipeline_qdrant.py`

```python
COLLECTION = "demo_docs"  # Qdrant collection name
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Embedding model
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Reranking model
RESET = False  # Reset collection on startup
DEDUPE_BY_SOURCE = False  # Deduplicate by source instead of UID
```

### `tools.py`

```python
COLLECTION = "demo_docs"  # Qdrant collection name
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Embedding model
```

---

## Type Definitions

### Common Types

```python
from typing import List, Dict, Optional, Tuple
import numpy as np
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder

# Document structure
Document = Dict[str, str]  # {"id": str, "title": str, "text": str}

# Corpus entry structure
CorpusEntry = Dict[str, str]  # {"uid": str, "title": str, "text": str, "source": str}

# Search result structure
SearchResult = Dict[str, Any]  # {
#     "uid": str,
#     "score": float,
#     "rerank_score": Optional[float],
#     "title": str,
#     "text": str,
#     "source": str
# }
```

---

## Error Handling

Most functions do not include explicit error handling in this demo implementation. For production use, consider:

- Wrapping Qdrant operations in try-except blocks
- Validating input parameters
- Handling model loading failures
- Graceful degradation when optional components (reranker, BM25) are unavailable

---

## Performance Considerations

1. **Embedding Model**: Larger models (e.g., `all-mpnet-base-v2`) provide better accuracy but slower inference
2. **HNSW Parameters**: Tune `m`, `ef_construct`, and `ef_search` based on dataset size and latency requirements
3. **Reranking**: Adds significant latency; use only when precision is critical
4. **MMR Diversity**: Higher diversity reduces redundancy but may lower relevance
5. **Batch Processing**: Consider batching embedding generation for large corpora

---

## License

This API documentation is provided as-is for the demonstration project.
