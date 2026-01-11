# Architecture Details

## System Components

### 1. Ingestion Layer

**Purpose**: Normalize articles from various sources into a common format.

**Components**:
- `Ingestor` base interface
- `RSSIngestor`: Robust RSS parsing with content extraction
- `YleIngestor`: Scaffold for Yle API (mock mode available)

**Flow**:
1. Fetch articles from source
2. Extract and clean content (HTML parsing, full-page fetch)
3. Normalize to `Article` dataclass
4. Return `IngestResult` with metadata

**Features**:
- Retry logic for network failures
- Timeout handling
- Best-effort content extraction
- Error tracking

### 2. Indexing Layer

**Purpose**: Chunk articles and store in Qdrant with stable IDs.

**Components**:
- `chunk()`: Sentence-based chunking with metadata
- `build_corpus_from_articles()`: Create corpus with metadata
- `index_articles()`: Embed and store in Qdrant

**Key Design Decisions**:
- **Deterministic Chunking**: Same article always produces same chunks
- **Stable IDs**: `uuid5(url + published_at + chunk_index)` ensures idempotency
- **Metadata**: Store chunk_index, char_start, char_end for traceability
- **Incremental Re-index**: Avoid duplicates via deterministic IDs

### 3. Retrieval Pipeline

**Purpose**: Find relevant chunks for a query.

**Components**:
- `hybrid_search()`: Main retrieval function
- Vector search (Qdrant)
- Optional BM25 keyword search
- MMR selection for diversity
- Cross-encoder reranking

**Flow**:
1. Vector search in Qdrant (top_k * 3 candidates)
2. Optional BM25 search on candidates
3. Hybrid score fusion (weighted combination)
4. MMR selection for diversity
5. Reranking with cross-encoder
6. Return top_k results

**Parameters**:
- `top_k`: Final number of results
- `mmr_k`: Number for MMR selection
- `score_threshold`: Minimum similarity
- `use_bm25`: Enable hybrid search
- `bm25_weight`: Weight for BM25 in fusion

### 4. Citation System

**Purpose**: Ensure every answer cites sources.

**Components**:
- `assign_source_labels()`: Assign [S1], [S2] labels
- `build_cited_prompt()`: Build prompt with source context
- `check_answerability()`: Gate for insufficient sources
- `check_citation_coverage()`: Validate citations in answer

**Flow**:
1. Assign stable labels to unique sources
2. Build prompt with labeled context
3. Generate answer with LLM
4. Check citation coverage
5. Return warnings if coverage insufficient

### 5. LLM Integration

**Purpose**: Generate answers with citations.

**Components**:
- `LLM` class: Mistral AI integration
- Prompt construction with source context
- Temperature and token limits

**Prompt Structure**:
- System instructions (ignore source instructions, cite everything)
- Question
- Context with source labels
- Source reference list

### 6. Audit System

**Purpose**: Complete audit trail of all operations.

**Database Schema**:
- `chat_runs`: Questions, answers, parameters, warnings, latency
- `retrieval_hits`: All retrieval results with scores
- `ingestion_runs`: Ingestion operations with counts and errors

**Features**:
- PostgreSQL for production
- SQLModel for type-safe ORM
- Alembic for migrations
- JSON fields for flexible metadata

### 7. Safety & Observability

**Safety**:
- Prompt injection detection
- Context sanitization
- Rate limiting
- CORS configuration

**Observability**:
- Structured JSON logging
- Request IDs for tracing
- Health/ready endpoints
- Latency tracking

## Data Flow

### Chat Request Flow

```
User Question
    │
    ▼
[API: /chat]
    │
    ├─── Rate Limiting Check
    ├─── Request Logging (with request_id)
    │
    ▼
[Retrieval Pipeline]
    ├─── Vector Search (Qdrant)
    ├─── BM25 (optional)
    ├─── MMR Selection
    ├─── Reranking
    │
    ▼
[Answerability Gate]
    ├─── Check confidence
    ├─── Check content length
    │
    ▼
[Citation System]
    ├─── Assign source labels
    ├─── Build prompt
    │
    ▼
[LLM Generation]
    ├─── Mistral API call
    │
    ▼
[Citation Coverage Check]
    ├─── Validate citations
    ├─── Generate warnings
    │
    ▼
[Audit Logging]
    ├─── Save to PostgreSQL
    │
    ▼
[Response]
    ├─── Answer
    ├─── Sources
    ├─── Hits
    ├─── Warnings
```

### Ingestion Flow

```
RSS Feed URL
    │
    ▼
[RSSIngestor]
    ├─── Parse feed
    ├─── Fetch full content (best-effort)
    ├─── Clean HTML
    │
    ▼
[Article Normalization]
    ├─── Extract metadata
    ├─── Create Article objects
    │
    ▼
[Indexing]
    ├─── Chunk articles
    ├─── Generate embeddings
    ├─── Store in Qdrant
    │
    ▼
[Audit Logging]
    ├─── Save ingestion run
    │
    ▼
[Response]
    └─── Count of indexed chunks
```

## Design Decisions

### Why Deterministic Chunking?

- Enables incremental re-indexing without duplicates
- Stable chunk IDs for traceability
- Predictable behavior for testing

### Why Hybrid Search?

- Vector search: Semantic similarity
- BM25: Keyword matching (good for names, dates)
- Fusion: Best of both worlds

### Why PostgreSQL for Audit?

- ACID guarantees
- Complex queries for analysis
- JSON fields for flexibility
- Production-ready

### Why Structured Logging?

- Easy parsing and analysis
- Request tracing
- Integration with log aggregation tools

## Future Enhancements

1. **More Ingestion Sources**: News APIs, web scraping
2. **Advanced Reranking**: Learned-to-rank models
3. **Multi-language**: Support for more languages
4. **User Authentication**: JWT/OAuth2
5. **Evaluation Dashboard**: Metrics visualization
6. **Streaming Responses**: Real-time answer generation
7. **Caching**: Redis for frequent queries
8. **Graph RAG**: Entity relationships
