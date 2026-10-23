# Transparent News Assistant

A production-grade demonstration of a responsible GenAI RAG (Retrieval-Augmented Generation) system with mandatory citations, comprehensive audit trails, safety controls, and a clean UI. This project showcases how to build trustworthy AI systems that are transparent, accountable, and safe.

## 🎯 Why This Matters

In an era of AI-generated content, transparency and accountability are critical. This system demonstrates:

- **Mandatory Citations**: Every factual claim must be backed by a source
- **Audit Trail**: Complete history of all queries, retrievals, and responses
- **Safety Controls**: Protection against prompt injection and malicious content
- **Answerability Gates**: Honest responses when sources are insufficient
- **Transparency UI**: Users can inspect retrieval results and system decisions

## ✨ Features

### Core Features

- ✅ **Adapter-Based Ingestion**: RSS feeds, Yle API (scaffold), extensible architecture
- ✅ **Stable Indexing**: Deterministic chunking with metadata (chunk_index, char positions)
- ✅ **Hybrid Retrieval**: Vector search + optional BM25 keyword search
- ✅ **MMR & Reranking**: Maximal Marginal Relevance for diversity, cross-encoder reranking
- ✅ **Mandatory Citations**: Every answer includes (S1), (S2) source markers
- ✅ **Answerability Gate**: Detects when sources are insufficient
- ✅ **Citation Coverage Check**: Validates that claims have citations
- ✅ **PostgreSQL Audit**: Complete audit trail with chat_runs, retrieval_hits, ingestion_runs
- ✅ **Safety Controls**: Prompt injection detection, rate limiting, CORS
- ✅ **Observability**: Structured logging, health/ready endpoints, latency tracking
- ✅ **React Frontend**: Clean UI with chat, transparency drawer, audit screen

### Responsible AI Features

- **Transparency**: Users can see all retrieval hits, scores, and warnings
- **Accountability**: Every interaction is logged with full context
- **Safety**: Multiple layers of protection against malicious inputs
- **Honesty**: System admits when it doesn't know or lacks sources

## 🖼️ User Interface

The application features a clean, transparent interface that shows users exactly how answers are generated:

![Chat Interface with Citations](docs/images/chat-interface.png)

**Key UI Features:**

- **Query Input**: Users can ask questions in natural language (Finnish or English)
- **Answer with Citations**: Every factual statement is backed by source references like `(S1)`, `(S2)`, etc.
- **Transparency Warnings**: The system displays warnings when:
  - Potentially uncited factual statements are detected
  - Citations reference non-existent sources
  - The answer may be missing a sources section
- **Source Display**: All retrieved sources are shown with:
  - Source labels (S1, S2, S3...)
  - Article titles
  - URLs
  - Publication dates and publishers
- **Audit Trail**: Users can view the complete history of queries and responses

This screenshot demonstrates the system answering a query about "venäjä" (Russia) with proper citations `(S1)`, `(S2)`, `(S3)` and displaying all retrieved sources below the answer. The warnings section helps users understand the quality and completeness of the generated response.

### Retrieval Transparency

The application provides full transparency into the retrieval process, showing users exactly which documents were retrieved and how relevant they are:

![Retrieval Hits with Scoring](docs/images/retrieval-hits-with-scoring.png)

**Retrieval Hits Features:**

- **Source Identifiers (S1, S2, S3)**: Each retrieved snippet is labeled with its source document. Multiple snippets can come from the same source article, allowing users to see different relevant passages from the same document.
- **Article Titles and Excerpts**: Each hit displays the article title and a relevant text excerpt, giving users immediate context about the retrieved information.
- **Dual Scoring System**: 
  - **Initial Score**: The similarity score from the vector database (Qdrant), typically ranging from 0.0 to 1.0
  - **Rerank Score**: A refined relevance score from the cross-encoder reranking model, which provides more accurate relevance assessment
- **Transparency Controls**: Users can expand or collapse the retrieval details, allowing them to inspect the sources when needed while keeping the interface clean.

This transparency feature is a core component of responsible AI, enabling users to:
- Verify the information sources used by the LLM
- Understand why certain information was included in the answer
- Assess the relevance and quality of retrieved documents
- Build trust through complete visibility into the system's decision-making process

The screenshot shows multiple hits from sources S1, S2, and S3, each with their relevance scores, demonstrating how the system retrieves and ranks information before generating a response.

### Audit Trail

The application maintains a complete audit trail of all interactions, allowing users to review past queries and responses.

**Audit Trail Features:**

- **Complete History**: View all past queries, answers, and retrieval results
- **Run Details**: Each interaction is logged with:
  - The original question
  - The generated answer
  - All retrieved sources and their scores
  - Timestamps and metadata
  - Any warnings or errors
- **Transparency**: Full visibility into how the system processed each query
- **Accountability**: Complete record for debugging, analysis, and compliance

The audit trail is essential for responsible AI, providing transparency and allowing users to understand how the system has responded to previous queries. When you first start the application, the audit trail will be empty ("No runs yet."), but it will populate as you interact with the system.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Chat Screen │  │ Transparency │  │ Audit Screen │          │
│  │             │  │   Drawer     │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   /chat      │  │ /ingest/rss  │  │   /runs      │          │
│  │   /health    │  │ /articles    │  │   /ready     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Ingestion Layer                                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│  │  │ RSS      │  │ Yle API  │  │ (Extend)  │              │  │
│  │  └──────────┘  └──────────┘  └──────────┘              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Retrieval Pipeline                                       │  │
│  │  1. Vector Search (Qdrant)                                 │  │
│  │  2. Optional BM25 (Hybrid)                                 │  │
│  │  3. MMR Selection (Diversity)                              │  │
│  │  4. Reranking (Cross-Encoder)                             │  │
│  │  5. Answerability Gate                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LLM + Citations                                          │  │
│  │  1. Build Prompt with Sources                             │  │
│  │  2. Generate Answer (vLLM/Ollama/Mistral)                  │  │
│  │  3. Citation Coverage Check                               │  │
│  │  4. Return with Warnings                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Safety & Observability                                  │  │
│  │  - Prompt Injection Detection                             │  │
│  │  - Rate Limiting                                          │  │
│  │  - Structured Logging                                      │  │
│  │  - Latency Tracking                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Qdrant     │    │  PostgreSQL  │    │ vLLM/Ollama/ │
│  (Vectors)   │    │   (Audit)    │    │   Mistral    │
└──────────────┘    └──────────────┘    └──────────────┘
```

## 🌐 Browser demo (GitHub Pages)

An interactive, **browser-only** portfolio demo of the Transparent News Assistant UI. It runs without Python, Qdrant, PostgreSQL, Docker, API keys, or an LLM service.

**Expected URL after you deploy:** https://karinehei.github.io/qdrant_transparent_news_assistant/

This repository does **not** claim the demo is already live; publish it manually when ready (steps below).

### What the demo shows

- Prepared scenarios: supported multi-source answers, insufficient evidence, citation warnings, and prompt-injection handling
- Clickable citations, expandable retrieval details with illustrative scores, warnings, and a local audit history
- A persistent banner: *Interactive demo · Prepared examples · No live AI or news retrieval*

### What is prepared or simulated

- Answers, sources, excerpts, and scores are **deterministic synthetic data** (fictional articles; illustrative scores only)
- Safety and citation examples **illustrate** behavior; they do **not** execute the backend’s safety or citation checks
- Free-text is limited to documented example questions; unmatched input gets a clear “not supported” message (never an unrelated canned answer)

### Demo mode vs full application

| | Browser demo | Full stack |
|---|---|---|
| Enable | `VITE_DEMO_MODE=true` (demo build only) | Default frontend + API |
| Data | Local prepared scenarios + `sessionStorage` | Live retrieval, LLM, audit DB |
| Network | No backend / RSS / LLM calls | `VITE_API_URL` HTTP API |

Normal builds keep the existing backend integration. Demo mode is never selected automatically after a backend failure.

### Local demo build and preview

```bash
cd web
npm ci
npm run build:demo
npm run preview:demo
```

Open the preview URL and append the repo base path if needed, e.g. `http://localhost:4173/qdrant_transparent_news_assistant/`.

### Publish to GitHub Pages (manual)

1. In the GitHub repo: **Settings → Pages → Build and deployment → Source**: GitHub Actions
2. Actions → **Deploy GitHub Pages demo** → **Run workflow** (`workflow_dispatch` only)
3. After success, open https://karinehei.github.io/qdrant_transparent_news_assistant/

The workflow builds only `web/` with `npm run build:demo` and uploads `web/dist` (no backend, env files, or credentials).

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)

### 1. Clone and Setup

```bash
git clone <repo-url>
cd qdrant_transparent_news_assistant
```

### 2. Configure Environment

Create a `.env` file:

```bash
# LLM Provider: Use vLLM (fast, GPU), Ollama (free, local), or Mistral API
LLM_PROVIDER=vllm  # "vllm" (GPU, 10-20x faster), "ollama" (CPU/GPU), or "mistral" (API)
# VLLM_BASE_URL=http://localhost:8001  # if using vLLM (requires GPU, port 8001 to avoid conflict with API on 8000)
# VLLM_MODEL=microsoft/Phi-3-mini-4k-instruct  # if using vLLM
# OLLAMA_MODEL=phi:latest  # if using Ollama: "phi:latest" (~1.6GB), "tinyllama" (~637MB)
# OLLAMA_BASE_URL=http://localhost:11434  # if using Ollama
# MISTRAL_API_KEY=your_mistral_api_key_here  # if using Mistral API
QDRANT_URL=http://localhost:6333
AUDIT_DB_URL=postgresql://news_user:news_pass@localhost:5432/news_audit
```

### 3. Start Services

```bash
# Start all services (PostgreSQL, Qdrant, API)
make up

# Or manually:
docker-compose up -d
```

### 4. Initialize Database

```bash
make init-db

# Or manually:
docker-compose exec api python -c "from news_assistant.audit_db import get_engine, init_db; from news_assistant.settings import settings; engine = get_engine(settings.audit_db_url); init_db(engine)"
```

### 5. Ingest Sample Data

```bash
make ingest

# Or manually:
curl -X POST http://localhost:8000/ingest/rss \
  -H "Content-Type: application/json" \
  -d '{"feed_url": "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET", "publisher": "Yle", "limit": 10}'
```

### 6. Start Frontend (Optional)

```bash
cd web
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`

### 7. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Mitä uutisia on tänään?"}'
```

## 📖 Usage

For detailed usage instructions, see [Usage Guide](docs/usage.md).

### API Endpoints

#### `POST /chat`
Ask a question about ingested news.

**Request:**
```json
{
  "question": "What are the latest news?"
}
```

**Response:**
```json
{
  "answer": "Based on sources (S1), (S2)...",
  "sources": [
    {
      "label": "S1",
      "title": "Article Title",
      "url": "https://...",
      "published_at": "2024-01-01T12:00:00",
      "publisher": "Yle"
    }
  ],
  "hits": [...],
  "run_id": 123,
  "warnings": []
}
```

#### `POST /ingest/rss`
Ingest articles from an RSS feed.

**Request:**
```json
{
  "feed_url": "https://feeds.example.com/rss",
  "publisher": "Example News",
  "limit": 30
}
```

#### `GET /runs`
List recent chat runs (audit trail).

#### `GET /runs/{id}`
Get details of a specific run.

#### `DELETE /articles`
Delete an article by URL or article_id.

For more detailed usage instructions, see the [Usage Guide](docs/usage.md).

### Makefile Commands

```bash
make up          # Start all services
make down        # Stop all services
make build       # Build containers
make test        # Run tests
make lint        # Lint code
make format      # Format code
make ingest      # Ingest sample RSS feed
make demo        # Run demo chat query
make clean       # Clean up volumes and caches
make init-db     # Initialize database schema
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_citations.py -v

# With coverage
pytest tests/ --cov=news_assistant --cov-report=html
```

## 📁 Project Structure

```
qdrant_transparent_news_assistant/
├── news_assistant/          # Main application
│   ├── api.py               # FastAPI endpoints
│   ├── settings.py          # Configuration
│   ├── audit_db.py          # PostgreSQL models
│   ├── qdrant_store.py      # Vector indexing
│   ├── retrieval.py         # Hybrid search
│   ├── citations.py         # Citation logic
│   ├── safety.py            # Safety checks
│   ├── llm.py               # LLM integration (vLLM/Ollama/Mistral)
│   ├── middleware.py        # Rate limiting, CORS
│   ├── intent.py            # Query intent detection
│   └── ingestors/           # Ingestion adapters
│       ├── base.py          # Base interface
│       ├── rss.py           # RSS ingestor
│       └── yle.py           # Yle API (scaffold)
├── scripts/                 # Utility scripts
│   ├── run_news_api.py      # API entry point
│   ├── tools.py             # CLI tool for indexing/searching
│   ├── demo.sh              # Demo script
│   ├── make.ps1             # PowerShell Makefile
│   ├── fix_docker_creds.*   # Docker credential fix scripts
│   └── legacy/              # Legacy demo scripts (reference only)
│       ├── mini_rag_pipeline_qdrant.py
│       ├── document_processing.py
│       ├── indexing.py
│       ├── retrieval.py
│       ├── prompting.py
│       └── config.py
├── docs/                    # Documentation
│   ├── architecture.md      # System architecture
│   ├── deployment.md         # Deployment guide
│   ├── rag_implementation.md # RAG implementation details
│   ├── security.md          # Security documentation
│   ├── usage.md             # Usage guide
│   ├── vllm_setup.md        # vLLM setup guide
│   ├── API.md               # API documentation
│   └── IMPLEMENTATION_SUMMARY.md
├── web/                     # React frontend
│   ├── src/
│   │   ├── components/      # React components
│   │   └── types/           # TypeScript types
│   └── package.json
├── tests/                   # Test suite
├── utils/                   # Utility modules
│   ├── groundedness_proxy.py
│   ├── latency_utils.py
│   └── metrics_relevance.py
├── alembic/                 # Database migrations
├── docker-compose.yml       # Local development
├── Dockerfile              # API container
├── Makefile                # Convenience commands
├── requirements.txt        # Python dependencies
├── pyproject.toml         # Project configuration
└── README.md               # This file
```

## 🔒 Security & Privacy

- **No PII Logging**: User queries are logged but no personal data is stored
- **Secret Management**: All secrets via environment variables
- **Rate Limiting**: Prevents abuse (100 requests/minute per IP)
- **Prompt Injection Defense**: Pattern-based detection + sanitization
- **CORS**: Configured for frontend origins only

See `docs/security.md` for detailed threat model.

## 🚢 Deployment

### AWS Deployment

1. **Container Registry**: Push Docker image to ECR
2. **ECS/Fargate**: Deploy API container
3. **RDS**: PostgreSQL for audit database
4. **Qdrant**: Deploy on ECS or use managed alternative
5. **ALB**: Load balancer with health checks
6. **CloudFront**: CDN for frontend (S3 + CloudFront)

See `docs/deployment.md` for detailed instructions.

### Environment Variables

```bash
# LLM Configuration (use Ollama for free local models)
LLM_PROVIDER=ollama
OLLAMA_MODEL=phi  # Fast model (~1.6GB), or "tinyllama" for even faster
# Or use Mistral API:
# LLM_PROVIDER=mistral
# MISTRAL_API_KEY=xxx

QDRANT_URL=http://qdrant:6333
AUDIT_DB_URL=postgresql://user:pass@rds-endpoint:5432/db
```

## 📊 Demo Scenarios

### Scenario 1: Basic Question
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Mitä uutisia on tänään?"}'
```

### Scenario 2: Specific Topic
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Kerro viimeisimmistä teknologiauutisista"}'
```

### Scenario 3: Insufficient Sources
```bash
# Ask about something not in the index
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Mitä tapahtui vuonna 1800?"}'
# Should return "I don't know" response
```

## 🛠️ Development

### Code Quality

```bash
# Format code
black news_assistant/ tests/
ruff check --fix news_assistant/ tests/

# Type checking
mypy news_assistant/

# Lint
ruff check news_assistant/ tests/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 🔧 Key Improvements & Fixes

The system includes several important improvements for reliability and accuracy:

### Latest Intent Detection ✅
- Detects queries like "viimeinen uutinen", "viimeisin uutinen", "uusin uutinen", "latest news", "most recent"
- Returns **ONLY the newest source** when latest intent is detected
- Sorts sources by `published_at` timestamp (missing timestamps treated as oldest)

### Citation Format ✅
- Uses `(S1)`, `(S2)` format for inline citations (changed from `[S1]`)
- Audit system recognizes both formats for backward compatibility
- Prompt explicitly instructs LLM to use `(S1)` format

### Prompt Leakage Prevention ✅
- Automatically removes instruction text from LLM responses
- Strips markers like "Käytä suomeksi", "VASTAUSOHJE:", "System:", etc.
- Ensures clean, user-facing answers without internal instructions

### URL Validation ✅
- Validates all URLs must start with `http://` or `https://`
- Invalid URLs are not displayed (logged as warning)
- Title and timestamp still shown even if URL is invalid

### Enhanced Audit System ✅
- Recognizes `(S1)` format citations (primary)
- Still supports `[S1]` format (backward compatibility)
- Ignores procedural sentences and "Lähteet:" headings
- Only flags >70% uncited statements as CRITICAL

### Topic-Based Filtering ✅
- Extracts topics from queries like "uutiset terveydestä", "uutiset taloudesta"
- Two-stage filtering: candidates → selected sources
- Combines topic + geographic relevance (e.g., "terveydestä Suomi")
- Returns only relevant sources (no padding with unrelated items)

These improvements ensure the system provides accurate, well-cited answers with proper source filtering and validation.

## 📚 Documentation

- [API Reference](API.md)
- [Usage Guide](docs/usage.md) - How to use the web interface and API
- [Security & Threat Model](docs/security.md)
- [Deployment Guide](docs/deployment.md)
- [Architecture Details](docs/architecture.md)
- [vLLM Setup Guide](docs/vllm_setup.md) - **10-20x faster than Ollama (requires GPU)**
- [RAG Implementation](docs/rag_implementation.md) - **Complete RAG pipeline documentation**
- [SQLModel Relationships Guide](docs/sqlmodel_relationships.md) - Troubleshooting relationship configuration issues
- [Troubleshooting Guide](docs/troubleshooting.md) - Common issues and solutions (CORS, Qdrant API, SQLAlchemy)

## 🤝 Contributing

This is a demonstration project. For production use, consider:

- Adding comprehensive integration tests
- Implementing Redis for rate limiting
- Adding monitoring (Prometheus, Grafana)
- Supporting more ingestion sources
- Implementing user authentication
- Adding evaluation metrics dashboard

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- [Qdrant](https://qdrant.tech/) - Vector database
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [vLLM](https://github.com/vllm-project/vllm) - High-performance LLM inference engine
- [Microsoft Phi-3](https://www.microsoft.com/en-us/research/blog/phi-3-mini/) - LLM models (Phi-3-mini-4k-instruct)
- [SentenceTransformers](https://www.sbert.net/) - Embeddings
