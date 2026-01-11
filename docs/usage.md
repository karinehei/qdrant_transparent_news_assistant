# Usage Guide

## Using the Web Interface

The easiest way to use the application is through the web interface:

1. **Start the Application**: Follow the Quick Start guide in README.md to start all services
2. **Open the Web Interface**: Navigate to `http://localhost:3000` in your browser
3. **Ask Questions**: 
   - Type your question in the search bar (supports Finnish and English)
   - Click "Ask" or press Enter
   - The system will retrieve relevant sources and generate an answer with citations
4. **View Sources**: 
   - Scroll down to see all retrieved sources
   - Click "Show Retrieval Details" to see the full retrieval hits with scores
   - Each source shows the title, URL, and publication date
5. **Check Warnings**: 
   - Review any warnings about citation coverage
   - Warnings help you understand the quality of the generated answer
6. **View Audit Trail**: 
   - Click the "Audit" button in the top navigation
   - Review all past queries and responses
   - See complete details of how each query was processed

## Example Queries

Try asking questions like:
- "Mitä uutisia on tänään?" (What news is there today?)
- "Kerro viimeisimmistä teknologiauutisista" (Tell me about the latest technology news)
- "Mitä tapahtui Venäjällä viime aikoina?" (What has happened in Russia recently?)
- "What are the latest developments in AI?"
- "uutiset terveydestä" (news about health)
- "terveydestä Suomi" (health Finland)
- "viimeinen uutinen" (latest news)

## Quick Reference: Common Operations

**Starting the Application:**
```bash
# Start all services (PostgreSQL, Qdrant, API)
make up

# Start vLLM server (if using vLLM, in a separate terminal)
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/Phi-3-mini-4k-instruct \
    --port 8001 \
    --host 0.0.0.0

# Start frontend (in web/ directory)
cd web && npm run dev
```

**Ingesting News Articles:**
```bash
# Ingest from RSS feed
make ingest

# Or manually with custom feed
curl -X POST http://localhost:8000/ingest/rss \
  -H "Content-Type: application/json" \
  -d '{"feed_url": "https://feeds.example.com/rss", "publisher": "Example News", "limit": 20}'
```

**Checking Status:**
```bash
# Health check
curl http://localhost:8000/health

# View API logs
docker logs news_api

# View recent audit runs
curl http://localhost:8000/runs
```

**Stopping the Application:**
```bash
# Stop all services
make down

# Stop and remove volumes (clean slate)
make clean
```

## Topic-Based Queries

The system supports topic-based filtering:

- **Topic queries**: "uutiset terveydestä" (news about health)
- **Geo filtering**: "terveydestä Suomi" (health Finland)
- **Latest news**: "viimeinen uutinen" (latest news)

The system will:
1. Extract topic and/or geographic filter from your query
2. Fetch candidate sources (30-50 items)
3. Filter by relevance to topic + geo
4. Return only selected, relevant sources
5. Generate answer with inline citations `(S1)`, `(S2)`, etc.

## Understanding the Response

**Answer Format:**
- Bullet points with inline citations: `(S1)`, `(S2)`, etc.
- Each factual statement is backed by a source
- Sources section lists all cited sources

**Sources List:**
- Shows only selected sources (those used in the answer)
- Each source includes: label (S1, S2...), title, URL, publication date
- Click URLs to view original articles

**Retrieval Details:**
- Click "Show Retrieval Details" to see:
  - All retrieval hits with relevance scores
  - Initial vector similarity scores
  - Rerank scores (if reranking enabled)
  - Full text snippets from retrieved documents

**Warnings:**
- Citation coverage warnings indicate if some statements lack citations
- Non-existent source warnings indicate citation errors
- These help you assess answer quality
