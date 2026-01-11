# RAG Implementation in Transparent News Assistant

This project implements a **complete RAG (Retrieval-Augmented Generation) pipeline** with production-grade features.

## RAG Pipeline Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG PIPELINE                             │
└─────────────────────────────────────────────────────────────┘

1. RETRIEVAL
   ├─ Query: "What happened with Trump?"
   ├─ Embed query → Vector search in Qdrant
   ├─ Optional: BM25 keyword search (hybrid)
   ├─ MMR for diversity
   ├─ Cross-encoder reranking
   └─ Returns: Top-K relevant chunks

2. AUGMENTATION
   ├─ Format retrieved chunks with source labels [S1], [S2]...
   ├─ Build prompt with question + context
   ├─ Add citation instructions
   └─ Safety checks (sanitization, suspicious content)

3. GENERATION
   ├─ Send augmented prompt to LLM (vLLM/Ollama/Mistral)
   ├─ LLM generates answer with citations
   └─ Validate citation coverage

4. VALIDATION
   ├─ Check answerability (sources sufficient?)
   ├─ Check citation coverage (all claims cited?)
   └─ Return answer + sources + warnings
```

## Implementation Details

### 1. Retrieval (`news_assistant/retrieval.py`)

**Hybrid Search:**
```python
hits = hybrid_search(
    qdrant,
    collection,
    embed_model,
    question,
    top_k=12,           # Final results
    mmr_k=6,            # MMR diversity selection
    score_threshold=0.25,  # Minimum relevance
    use_bm25=False,     # Optional keyword search
    rerank_model=rerank_model,  # Optional reranking
)
```

**Features:**
- **Vector Search**: Semantic similarity using embeddings
- **BM25 Search**: Keyword-based search (optional, hybrid mode)
- **MMR (Maximal Marginal Relevance)**: Balances relevance and diversity
- **Reranking**: Cross-encoder for better relevance ordering
- **Score Filtering**: Removes low-relevance results

### 2. Augmentation (`news_assistant/citations.py`)

**Prompt Building:**
```python
hits_labeled, sources = assign_source_labels(hits)
prompt = build_cited_prompt(question, hits_labeled, sources)
```

**Prompt Structure:**
```
Olet läpinäkyvä uutisavustaja. Vastaa vain annetun kontekstin perusteella.

KYSYMYS:
{question}

KONTEKSTI:
[S1] Title: {chunk_text_1}
[S2] Title: {chunk_text_2}
...

VASTAUSOHJE:
- 3–6 napakkaa bullet-kohtaa suomeksi.
- Jokaisen faktaväitteen perässä pitää olla lähdeviite [S1], [S2]...
- Lopussa otsikko 'Lähteet:' ja listaa vain lähteet, joihin viittasit.

LÄHTEET (viitelista):
[S1] Title — URL — Publisher — Date
[S2] Title — URL — Publisher — Date
```

### 3. Generation (`news_assistant/llm.py`)

**LLM Call:**
```python
llm = _llm()  # vLLM, Ollama, or Mistral
answer = llm.generate(prompt, max_tokens=200)
```

**Supported Providers:**
- **vLLM**: Fast, GPU-optimized (2-5s)
- **Ollama**: Free, local (60-120s CPU, 10-30s GPU)
- **Mistral API**: Cloud service

### 4. Validation (`news_assistant/citations.py`)

**Answerability Gate:**
```python
can_answer, reason = check_answerability(hits, score_threshold=0.25)
if not can_answer:
    return "En tiedä vastausta nykyisten lähteiden perusteella..."
```

**Citation Coverage Check:**
```python
has_coverage, warnings = check_citation_coverage(answer, sources)
if not has_coverage:
    warnings.extend(coverage_warnings)
```

## Complete RAG Flow

### Step-by-Step in Code

**File: `news_assistant/api.py` (chat endpoint)**

```python
# 1. RETRIEVAL
hits = hybrid_search(
    qdrant, collection, embed_model, question,
    top_k=12, mmr_k=6, score_threshold=0.25,
    use_bm25=False, rerank_model=rerank_model,
)

# 2. SAFETY & ANSWERABILITY
suspicious = any_context_is_suspicious([h.get("payload",{}).get("text","") for h in hits])
can_answer, reason = check_answerability(hits, score_threshold=settings.score_threshold)

if not can_answer:
    return "En tiedä vastausta..."  # Early exit if no good sources

# 3. AUGMENTATION
hits_labeled, sources = assign_source_labels(hits)
prompt = build_cited_prompt(question, hits_labeled, sources)

# 4. GENERATION
llm = _llm()
answer = llm.generate(prompt, max_tokens=settings.max_answer_tokens)

# 5. VALIDATION
has_coverage, coverage_warnings = check_citation_coverage(answer, sources)
if not has_coverage:
    warnings.extend(coverage_warnings)

# 6. RETURN
return ChatResponse(
    answer=answer,
    sources=sources,
    hits=hits,
    warnings=warnings,
)
```

## RAG Components

### Retrieval Components

| Component | File | Purpose |
|-----------|------|---------|
| **Hybrid Search** | `retrieval.py` | Vector + BM25 search |
| **MMR Selection** | `retrieval.py` | Diversity optimization |
| **Reranking** | `retrieval.py` | Cross-encoder reranking |
| **Qdrant Store** | `qdrant_store.py` | Vector database operations |

### Augmentation Components

| Component | File | Purpose |
|-----------|------|---------|
| **Prompt Builder** | `citations.py` | Builds RAG prompt with context |
| **Source Labeling** | `citations.py` | Assigns [S1], [S2] labels |
| **Safety** | `safety.py` | Sanitizes context |

### Generation Components

| Component | File | Purpose |
|-----------|------|---------|
| **LLM Client** | `llm.py` | vLLM/Ollama/Mistral integration |
| **Settings** | `settings.py` | LLM provider configuration |

### Validation Components

| Component | File | Purpose |
|-----------|------|---------|
| **Answerability** | `citations.py` | Checks if sources are sufficient |
| **Citation Coverage** | `citations.py` | Validates citations in answer |

## RAG Features

### ✅ Standard RAG

- ✅ **Vector Search**: Semantic similarity
- ✅ **Context Augmentation**: Retrieved chunks in prompt
- ✅ **LLM Generation**: Answer based on context
- ✅ **Source Attribution**: Citations in answer

### ✅ Advanced RAG

- ✅ **Hybrid Search**: Vector + BM25 keyword search
- ✅ **MMR**: Maximal Marginal Relevance for diversity
- ✅ **Reranking**: Cross-encoder for better ordering
- ✅ **Answerability Gate**: Checks if sources are sufficient
- ✅ **Citation Validation**: Ensures all claims are cited

### ✅ Production RAG

- ✅ **Safety Checks**: Prompt injection defense, content sanitization
- ✅ **Audit Trail**: Complete logging of retrievals and generations
- ✅ **Transparency**: Users can see all retrieval hits
- ✅ **Error Handling**: Graceful degradation when sources insufficient

## RAG vs Simple LLM

| Feature | Simple LLM | This RAG System |
|---------|------------|-----------------|
| **Knowledge** | Training data only | **Up-to-date news articles** |
| **Citations** | None | **Mandatory [S1], [S2] citations** |
| **Transparency** | Black box | **Full retrieval visibility** |
| **Accuracy** | Can hallucinate | **Grounded in sources** |
| **Audit** | No tracking | **Complete audit trail** |

## RAG Pipeline Metrics

The system tracks:
- **Retrieval latency**: Time to find relevant chunks
- **Generation latency**: Time for LLM to generate answer
- **Total latency**: End-to-end response time
- **Retrieval scores**: Relevance scores for each hit
- **Citation coverage**: Whether all claims are cited

## Example RAG Flow

**Query:** "What happened with Trump?"

1. **Retrieval** (0.5s):
   - Embed query: `[0.1, 0.2, ...]`
   - Search Qdrant: Find 12 relevant chunks
   - MMR: Select 6 diverse chunks
   - Rerank: Order by relevance

2. **Augmentation** (0.01s):
   - Format chunks with [S1], [S2] labels
   - Build prompt with question + context

3. **Generation** (2-5s with vLLM, 60-120s with Ollama):
   - LLM generates answer with citations
   - Example: "Trump announced... [S1] According to [S2]..."

4. **Validation** (0.01s):
   - Check citation coverage
   - Return answer + sources + warnings

## See Also

- [Architecture Details](architecture.md)
- [Retrieval Implementation](retrieval.py)
- [Citation System](citations.py)
- [API Endpoints](API.md)
