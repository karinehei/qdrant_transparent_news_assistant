from __future__ import annotations
import time
import logging
import re
import json
from collections import Counter
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder

from .settings import settings
from .middleware import setup_cors, RequestLoggingMiddleware, RateLimitMiddleware

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)
from .ingestors import RSSIngestor, Article
from .qdrant_store import ensure_collection, index_articles, delete_article_by_url, delete_article_by_id
from .retrieval import hybrid_search
from .citations import assign_source_labels, build_cited_prompt, check_answerability, check_citation_coverage, SourceRef
from .intent import detect_intent, sort_sources_by_timestamp, parse_query_intent, QueryIntent, STOPWORDS_FI
from .safety import sanitize_context, any_context_is_suspicious
from .llm import LLM
from .audit_db import (
    get_engine, init_db, ChatRun, RetrievalHit, IngestionRun,
    save_run, save_ingestion_run, list_runs, read_run
)
from .schemas import IngestRequest, IngestResponse, ChatRequest, ChatResponse, SourceItem, HitItem, RunItem, DeleteArticleRequest, DeleteArticleResponse

app = FastAPI(title="Transparent News Assistant", version="0.1.0")

# Setup middleware
setup_cors(app)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

# Lazy singletons
qdrant = QdrantClient(url=settings.qdrant_url)
embed_model = SentenceTransformer(settings.embed_model)
rerank_model = CrossEncoder(settings.rerank_model) if settings.use_rerank else None
ensure_collection(qdrant, settings.qdrant_collection, dim=embed_model.get_sentence_embedding_dimension())

engine = get_engine(settings.audit_db_url)
init_db(engine)

def _remove_repetitions(text: str) -> str:
    """
    Remove obvious word/phrase repetitions that indicate the LLM got stuck in a loop.
    Detects patterns like "word word word word..." and replaces with single occurrence.
    Uses regex for better pattern matching.
    """
    if not text:
        return text
    
    # First, use regex to find and remove obvious word repetitions (same word 3+ times in a row)
    # Pattern: word followed by space and same word repeated 2+ more times
    # This catches cases like "kansainvälisen kansainvälisen kansainvälisen..."
    def remove_word_repetition(match):
        word = match.group(1)
        # Count how many times it repeats
        full_match = match.group(0)
        repeats = len(full_match.split())
        if repeats >= 3:
            logger.warning(f"Removed {repeats} repetitions of word '{word}'")
            return word  # Keep only first occurrence
        return full_match  # Keep as-is if less than 3 repeats
    
    # Match word followed by same word 2+ times (with spaces)
    # \b ensures word boundaries
    pattern = r'\b(\w+)(?:\s+\1){2,}'
    text = re.sub(pattern, remove_word_repetition, text)
    
    # Also handle phrase repetitions (2-3 word phrases)
    words = text.split()
    if len(words) >= 6:
        result = []
        i = 0
        while i < len(words):
            # Check for 2-word phrase repetition
            if i + 6 <= len(words):
                phrase = " ".join(words[i:i+2])
                # Check if this phrase repeats
                repeat_count = 1
                j = i + 2
                while j + 2 <= len(words):
                    next_phrase = " ".join(words[j:j+2])
                    if next_phrase == phrase:
                        repeat_count += 1
                        j += 2
                    else:
                        break
                
                if repeat_count >= 3:
                    # Found repeating phrase, keep only first occurrence
                    result.extend(words[i:i+2])
                    i = j
                    logger.warning(f"Removed {repeat_count} repetitions of phrase '{phrase}'")
                    continue
            
            result.append(words[i])
            i += 1
        text = " ".join(result)
    
    # Remove duplicate lines (same line repeated)
    lines = text.split('\n')
    seen_lines = set()
    unique_lines = []
    for line in lines:
        line_stripped = line.strip()
        if line_stripped and line_stripped not in seen_lines:
            seen_lines.add(line_stripped)
            unique_lines.append(line)
        elif not line_stripped:
            unique_lines.append(line)  # Keep empty lines
    
    return '\n'.join(unique_lines)


def _has_instruction_leakage(answer: str) -> bool:
    """Check if answer contains instruction leakage markers."""
    if not answer:
        return False
    
    leakage_markers = [
        'PAKOLLISET', 'KUNTAAN', 'KRIITTISET', 'SULKEITA', 'HAKASULKEITA',
        'VASTAUSOHJE', 'OHJEET', 'ÄLÄ', 'KÄYTÄ', 'TÄYTYY', 'System:'
    ]
    
    answer_upper = answer.upper()
    return any(marker in answer_upper for marker in leakage_markers)


def _remove_prompt_leakage(answer: str) -> str:
    """
    Remove instruction-like text that leaked from the prompt.
    Detects and removes common instruction phrases and policy text.
    """
    if not answer:
        return answer
    
    # Instruction markers that should never appear in user-facing answers
    instruction_markers = [
        r'PAKOLLISET',
        r'KUNTAAN',
        r'KRIITTISET\s+SÄÄNNÖT',
        r'VASTAUSOHJE',
        r'OHJEET\s+VASTAUKSEEN',
        r'KÄYTÄ\s+SULKEITA',
        r'EI\s+HAKASULKEITA',
        r'ÄLÄ\s+käytä',
        r'ÄLÄ\s+keksi',
        r'ÄLÄ\s+yritä',
        r'ÄLÄ\s+toista',
        r'^Käytä\s+suomeksi',
        r'^Vastaa\s+suomeksi',
        r'^Vastaa\s+selkeästi',
        r'Käytä\s+suomeksi\s+ja\s+informatiivisesti',
        r'Vastaa\s+suomeksi\s+selkeästi',
        r'System:',
        r'Assistant:',
        r'User:',
        r'^Ohje:',
        r'^Muista:',
        r'^Säännöt:',
        r'^Esimerkki:',
        r'^1\.\s+',
        r'^2\.\s+',
        r'^3\.\s+',
        r'^4\.\s+',
    ]
    
    # Also check for instruction keywords in the text
    instruction_keywords = [
        'PAKOLLISET', 'KUNTAAN', 'KRIITTISET', 'SULKEITA', 'HAKASULKEITA',
        'VASTAUSOHJE', 'OHJEET', 'ÄLÄ', 'KÄYTÄ', 'TÄYTYY'
    ]
    
    lines = answer.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            cleaned_lines.append(line)
            continue
        
        # Skip lines that match instruction markers
        is_instruction = any(re.search(marker, line_stripped, re.IGNORECASE) for marker in instruction_markers)
        
        # Also check if line contains too many instruction keywords
        keyword_count = sum(1 for kw in instruction_keywords if kw in line_stripped.upper())
        is_instruction_heavy = keyword_count >= 2
        
        if not is_instruction and not is_instruction_heavy:
            cleaned_lines.append(line)
    
    result = '\n'.join(cleaned_lines).strip()
    
    # If we removed too much (answer is too short), return original
    if len(result) < len(answer) * 0.3:
        return answer
    
    # Final check: if result still contains instruction keywords, try to extract just the answer part
    if any(kw in result.upper() for kw in ['PAKOLLISET', 'KUNTAAN', 'KRIITTISET']):
        # Try to find where the actual answer starts (after instruction blocks)
        lines_result = result.split('\n')
        answer_start = 0
        for i, line in enumerate(lines_result):
            if any(kw in line.upper() for kw in ['PAKOLLISET', 'KUNTAAN', 'KRIITTISET', 'VASTAUSOHJE', 'SÄÄNNÖT']):
                answer_start = i + 1
                break
        if answer_start > 0:
            result = '\n'.join(lines_result[answer_start:]).strip()
    
    # Remove any remaining instruction-like patterns
    # Remove lines that are just numbers or bullet points with instructions
    final_lines = []
    for line in result.split('\n'):
        line_stripped = line.strip()
        # Skip lines that are just instruction patterns
        if re.match(r'^[0-9]+\.\s*[A-ZÄÖÅ]', line_stripped):
            continue  # Skip numbered instruction lines
        if re.match(r'^-\s*[A-ZÄÖÅ]', line_stripped) and any(kw in line_stripped.upper() for kw in ['KÄYTÄ', 'ÄLÄ', 'TÄYTYY']):
            continue  # Skip bullet instruction lines
        final_lines.append(line)
    
    result = '\n'.join(final_lines).strip()
    
    return result


def _parse_structured_output(answer_raw: str, sources: List[SourceRef]) -> tuple[str, List[str]]:
    """
    Parse structured JSON output from LLM.
    
    Expected format:
    {
      "answer_fi": ["bullet 1 (S1)", "bullet 2 (S2)", ...],
      "sources_used": ["S1", "S2", ...]
    }
    
    Returns:
        (formatted_answer, sources_used_list) or (None, []) if parsing fails
    """
    
    # Try to extract JSON from answer
    # Look for JSON block (may be wrapped in markdown code blocks)
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', answer_raw, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{[^{}]*"answer_fi"[^{}]*\}', answer_raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            return None, []
    
    try:
        data = json.loads(json_str)
        answer_fi = data.get("answer_fi", [])
        sources_used = data.get("sources_used", [])
        
        if isinstance(answer_fi, list):
            # Join bullets with newlines
            formatted = "\n".join(f"- {bullet}" if not bullet.startswith("-") else bullet for bullet in answer_fi)
            return formatted, sources_used
        elif isinstance(answer_fi, str):
            # Single string answer
            return answer_fi, sources_used
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass
    
    return None, []


def _remove_bracket_citations(answer: str, sources: List[SourceRef]) -> str:
    """
    Remove bracket citations [S1] from answer - they're not valid.
    This prevents audit from flagging them as non-existent sources.
    """
    
    # Find all bracket citations
    bracket_citations = re.findall(r'\[S\d+\]', answer)
    
    if not bracket_citations:
        return answer
    
    # Remove bracket citations (don't convert - just remove to avoid confusion)
    # This prevents audit from flagging them as non-existent sources
    result = answer
    for bracket_cite in bracket_citations:
        result = result.replace(bracket_cite, '')
    
    # Clean up extra spaces
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'\s+([.!?])', r'\1', result)
    
    return result.strip()


def _validate_citations(answer: str, sources: List[SourceRef], warnings: List[str]) -> str:
    """
    Validate that all citations in answer reference existing sources.
    Remove invalid citations.
    """
    import re
    
    available_labels = {s.label for s in sources}
    
    # Find all citations
    citations = re.findall(r'\(S\d+\)', answer)
    cited_labels = {c.strip('()') for c in citations}
    
    # Find invalid citations
    invalid_labels = cited_labels - available_labels
    
    if invalid_labels:
        # Remove invalid citations
        for label in invalid_labels:
            answer = answer.replace(f"({label})", "")
        warnings.append(f"Removed citations to non-existent sources: {invalid_labels}")
        # Clean up extra spaces
        answer = re.sub(r'\s+', ' ', answer)
        answer = re.sub(r'\s+([.!?])', r'\1', answer)
    
    return answer.strip()


def _ensure_sources_section(answer: str, sources: List[SourceRef], sources_used: Optional[List[str]] = None) -> str:
    """
    Ensure the answer always includes a Sources section.
    If missing, append it with all sources that have citations in the answer.
    """
    import re
    
    answer_lower = answer.lower()
    has_sources_section = "lähteet:" in answer_lower or "sources:" in answer_lower
    
    if not has_sources_section and sources:
        # Use sources_used if provided (from JSON), otherwise extract from answer
        if sources_used:
            cited_labels_clean = set(sources_used)
        else:
            # Extract which sources were cited - support both (S1) and [S1] formats for extraction
            cited_with_parens = set(re.findall(r'\(S\d+\)', answer))
            cited_with_brackets = set(re.findall(r'\[S\d+\]', answer))
            cited_labels_clean = {label.strip('()') for label in cited_with_parens} | {label.strip('[]') for label in cited_with_brackets}
        
        # Find sources that were actually cited
        cited_sources = [s for s in sources if s.label in cited_labels_clean]
        
        if cited_sources:
            sources_lines = ["\nLähteet:"]
            for s in cited_sources:
                url = s.url or s.key or "N/A"
                sources_lines.append(f"- [{s.label}] {s.title} — {url}")
            answer = answer.rstrip() + "\n" + "\n".join(sources_lines)
        elif len(sources) > 0:
            # No citations but we have sources - list all as fallback
            sources_lines = ["\nLähteet:"]
            for s in sources:
                url = s.url or s.key or "N/A"
                sources_lines.append(f"- [{s.label}] {s.title} — {url}")
            answer = answer.rstrip() + "\n" + "\n".join(sources_lines)
    
    return answer


def _add_missing_citations(answer: str, sources: List[SourceRef], warnings: List[str]) -> str:
    """
    Attempt to automatically add citations to uncited factual statements.
    This is a best-effort approach - if too many citations are missing, we should refuse.
    """
    import re
    
    # Skip if answer is already a refusal message
    if "En voi vastata" in answer or "cannot answer" in answer.lower():
        return answer
    
    # Extract sentences more carefully (preserve punctuation)
    sentence_parts = re.split(r'([.!?]+)\s+', answer)
    
    # Recombine sentences with their punctuation
    sentences = []
    for i in range(0, len(sentence_parts) - 1, 2):
        if i + 1 < len(sentence_parts):
            sentences.append(sentence_parts[i] + sentence_parts[i + 1])
        else:
            sentences.append(sentence_parts[i])
    
    # Find sentences with factual indicators but no citations
    factual_indicators = [
        "on", "oli", "tapahtui", "sanoi", "kertoi", "mukaan", "vuonna", "vuosina",
        "is", "was", "happened", "said", "according", "year", "syntyi", "kuoli"
    ]
    
    uncited_sentences = []
    for i, sent in enumerate(sentences):
        sent_clean = sent.strip()
        if not sent_clean or len(sent_clean) < 10:  # Skip very short fragments
            continue
        # Skip Sources section
        if "lähteet:" in sent_clean.lower() or "sources:" in sent_clean.lower():
            continue
        sent_lower = sent_clean.lower()
        # Check if sentence looks factual
        if any(ind in sent_lower for ind in factual_indicators):
            # Check if it has a citation
            if not re.search(r'\[S\d+\]', sent_clean):
                uncited_sentences.append((i, sent_clean))
    
    # If too many uncited sentences, don't try to fix (would be unreliable)
    total_factual = len([s for s in sentences if any(ind in s.lower() for ind in factual_indicators)])
    if total_factual == 0:
        return answer  # No factual statements to cite
    
    uncited_ratio = len(uncited_sentences) / max(total_factual, 1)
    if uncited_ratio > 0.5:  # More than 50% uncited - don't auto-fix
        return answer  # Return as-is, let the warning handle it
    
    # For a few missing citations, try to add citations intelligently
    if uncited_sentences and sources:
        # Try to match uncited sentences to sources based on content similarity
        modified_sentences = sentences.copy()
        added_count = 0
        
        for idx, sent in uncited_sentences[:5]:  # Limit to first 5 to avoid over-citing
            # Find best matching source based on keyword overlap
            best_source = None
            best_score = 0
            
            sent_words = set(re.findall(r'\w+', sent.lower()))
            for source in sources:
                # Check title and URL for keywords
                title_words = set(re.findall(r'\w+', (source.title or "").lower()))
                overlap = len(sent_words & title_words)
                if overlap > best_score:
                    best_score = overlap
                    best_source = source
            
            # Use best matching source, or first source as fallback
            source_label = (best_source or sources[0]).label
            
            # Add citation at end of sentence (before punctuation) - use (S1) format
            if f"({source_label})" not in sent and f"[{source_label}]" not in sent:
                # Find the sentence in the original list
                original_sent = sentences[idx]
                # Add citation before final punctuation - use (S1) format
                sent_with_citation = re.sub(r'([.!?]+)\s*$', f' ({source_label})\\1', original_sent.rstrip())
                if sent_with_citation != original_sent:
                    modified_sentences[idx] = sent_with_citation
                    added_count += 1
        
        if added_count > 0:
            result = ''.join(modified_sentences)
            # Only add warning if we added multiple citations
            if added_count > 1:
                warnings.append(f"Automatically added {added_count} missing citations")
            return result
    
    return answer

# Log LLM provider configuration at startup
logger.info(f"LLM Provider configured: {settings.llm_provider}")
logger.info(f"vLLM Base URL: {settings.vllm_base_url}")
logger.info(f"Ollama Base URL: {settings.ollama_base_url}")

def _llm() -> LLM:
    """Initialize LLM based on provider setting."""
    # Ensure we're using the correct provider - force reload if needed
    # This helps catch cases where .env wasn't loaded properly
    provider = settings.llm_provider.lower().strip()
    
    # Safety check: if provider is still "ollama" but we want vllm, log a warning
    if provider == "ollama":
        logger.warning(f"LLM provider is set to 'ollama'. If you want to use vLLM, set LLM_PROVIDER=vllm in .env and restart the application.")
    
    if provider == "ollama":
        return LLM(
            provider="ollama",
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    elif provider == "vllm":
        return LLM(
            provider="vllm",
            model=settings.vllm_model,
            base_url=settings.vllm_base_url,
        )
    elif provider == "mistral":
        if not settings.mistral_api_key:
            raise HTTPException(
                status_code=500, 
                detail="MISTRAL_API_KEY missing in environment/.env. Set LLM_PROVIDER=ollama to use free local models."
            )
        return LLM(
            provider="mistral",
            model=settings.ollama_model if settings.llm_provider == "ollama" else (settings.vllm_model if settings.llm_provider == "vllm" else settings.mistral_model),
            api_key=settings.mistral_api_key,
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown LLM provider: {provider} (from settings: {settings.llm_provider}). Use 'ollama', 'vllm', or 'mistral'"
        )

@app.post("/ingest/rss", response_model=IngestResponse)
def ingest_rss(req: IngestRequest):
    import time
    start_time = time.time()
    
    ingestor = RSSIngestor()
    result = ingestor.fetch_articles(req.feed_url, publisher=req.publisher, limit=req.limit)
    
    # Convert Article objects to dict format for indexing
    articles_dict = [
        {
            "id": a.source_id or a.url,
            "url": a.url,
            "title": a.title,
            "text": a.text,
            "published_at": a.published_at,
            "publisher": a.publisher,
        }
        for a in result.articles
    ]
    n = index_articles(qdrant, settings.qdrant_collection, embed_model, articles_dict)
    
    # Save ingestion run to audit DB
    ingestion_run = IngestionRun(
        source_type=result.source_type,
        source_ref=result.source_ref,
        count_ingested=n,
        errors=result.errors,
        publisher=req.publisher,
    )
    save_ingestion_run(engine, ingestion_run)
    
    return IngestResponse(indexed_chunks=n)

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    import time
    import re  # Ensure re is available in function scope
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")
    
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question empty")
    
    logger.info("chat_request", extra={"request_id": request_id, "question": question[:100]})

    # Parse query intent and extract topic + geo
    query_intent = parse_query_intent(question)
    logger.info(f"Query intent: {query_intent.intent}, topic: {query_intent.topic}, geo: {query_intent.geo}")
    
    # Adjust retrieval based on intent
    if query_intent.intent == "latest":
        # For "latest news", fetch more candidates to find newest
        search_top_k = min(settings.top_k, 20)
        initial_candidates = 30
    elif query_intent.intent == "topic":
        # For topic queries, fetch many candidates for filtering
        search_top_k = settings.top_k
        initial_candidates = settings.topic_retrieval_candidates
    else:
        # General query
        search_top_k = settings.top_k
        initial_candidates = settings.top_k * 2

    # STAGE 1: Fetch initial candidates (more for filtering)
    candidates = hybrid_search(
        qdrant,
        settings.qdrant_collection,
        embed_model,
        question,
        top_k=initial_candidates,  # Fetch many candidates
        mmr_k=settings.mmr_k,
        score_threshold=settings.score_threshold,
        use_bm25=settings.use_bm25,
        rerank_model=rerank_model,
    )
    
    logger.info(f"Stage 1: Fetched {len(candidates)} candidates")
    
    # STAGE 2: Filter and rerank candidates by topic + geo relevance
    selected_hits = []
    
    if query_intent.intent == "topic" and (query_intent.topic or query_intent.geo) and candidates:
        from .citations import compute_query_relevance
        
        # Compute combined relevance (topic + geo)
        for h in candidates:
            payload = h.get("payload", {})
            text = payload.get("text", "")
            title = payload.get("title", "")
            vector_score = h.get("score")
            
            # Compute topic relevance
            topic_relevance = 0.0
            if query_intent.topic:
                topic_relevance = compute_query_relevance(
                    query_intent.topic,
                    text,
                    title,
                    embed_model=embed_model,
                    vector_score=vector_score
                )
            
            # Compute geo relevance (check if content mentions Finland)
            geo_relevance = 0.0
            if query_intent.geo == "FI":
                # Check for Finland-related keywords
                finland_keywords = ["suomi", "suomen", "suomessa", "finnish", "finland", "helsinki", "tampere", "turku"]
                content_lower = (title + " " + text).lower()
                matches = sum(1 for kw in finland_keywords if kw in content_lower)
                geo_relevance = min(1.0, matches / 3.0)  # Normalize to 0-1
            
            # Combine topic and geo relevance
            if query_intent.topic and query_intent.geo:
                # Both filters: weighted combination
                combined_relevance = 0.6 * topic_relevance + 0.4 * geo_relevance
            elif query_intent.topic:
                combined_relevance = topic_relevance
            elif query_intent.geo:
                combined_relevance = geo_relevance
            else:
                combined_relevance = vector_score if vector_score else 0.5
            
            h["combined_relevance"] = combined_relevance
            h["topic_relevance"] = topic_relevance
            h["geo_relevance"] = geo_relevance
            
            # Keep if above threshold
            if combined_relevance >= settings.topic_relevance_threshold:
                selected_hits.append(h)
        
        # Sort by combined relevance
        selected_hits.sort(key=lambda x: x.get("combined_relevance", 0.0), reverse=True)
        
        logger.info(f"Stage 2: Selected {len(selected_hits)}/{len(candidates)} sources (topic: {query_intent.topic}, geo: {query_intent.geo})")
        
        # Check if we have enough relevant sources
        if len(selected_hits) < settings.topic_min_sources:
            # Not enough relevant sources - ask for clarification
            # Extract keywords from all candidates for suggestions
            all_keywords = []
            for h in candidates[:20]:  # Look at top 20 for keyword extraction
                title = h.get("payload", {}).get("title", "")
                # Use string methods instead of re to avoid scoping issues
                words = [w for w in title.lower().split() if len(w) >= 4 and w.isalnum()]
                all_keywords.extend([w for w in words if w not in STOPWORDS_FI and len(w) > 3])
            
            # Get most common keywords
            keyword_counts = Counter(all_keywords)
            top_keywords = [kw for kw, _ in keyword_counts.most_common(3)]
            
            # Generic topic suggestions
            generic_suggestions = ["Suomi", "maailma", "politiikka", "talous", "tiede", "urheilu"]
            suggestions = top_keywords[:2] + generic_suggestions[:2]
            suggestions = list(dict.fromkeys(suggestions))[:3]  # Remove duplicates, limit to 3
            
            answer = (
                f"En löytänyt tarpeeksi uutisia aiheesta '{query_intent.topic}' nykyisistä lähteistä. "
                f"Löysin vain {len(relevant_hits)} relevanttia lähdettä (tarvitaan vähintään {settings.topic_min_sources}).\n\n"
                f"Voitko tarkentaa kysymystäsi? Esimerkiksi:\n"
                + "\n".join(f"- {query_intent.topic} {s}" for s in suggestions)
            )
            warnings = [f"Insufficient relevant sources for topic '{query_intent.topic}'"]
            
            # Determine model name
            if settings.llm_provider.lower() == "ollama":
                model_name = settings.ollama_model
            elif settings.llm_provider.lower() == "vllm":
                model_name = settings.vllm_model
            elif settings.llm_provider.lower() == "mistral":
                model_name = settings.mistral_model
            else:
                model_name = settings.vllm_model
            
            run = ChatRun(
                question=question,
                answer=answer,
                model=model_name,
                embed_model=settings.embed_model,
                rerank_model=settings.rerank_model if settings.use_rerank else None,
                top_k=settings.top_k,
                mmr_k=settings.mmr_k,
                score_threshold=settings.score_threshold,
                suspicious_context=False,
            )
            saved = save_run(engine, run, [])
            return ChatResponse(
                answer=answer,
                sources=[],
                hits=[],
                run_id=saved.id,  # type: ignore
                warnings=warnings,
            )
        
        # Take top K selected sources
        selected_hits = selected_hits[:search_top_k]
        hits = selected_hits
    else:
        # No topic/geo filtering - use all candidates (but limit to search_top_k)
        hits = candidates[:search_top_k]
    
    # If latest intent, sort by timestamp and take only the newest
    if query_intent.intent == "latest" and hits:
        hits = sort_sources_by_timestamp(hits, reverse=True)
        hits = hits[:1]  # Take only the newest one
        logger.info(f"Latest intent detected: returning only newest source")
    
    # Validate that we only use sources that exist
    # This prevents citing non-existent sources
    if not hits:
        logger.warning("No hits retrieved for query")

    # sanitize chunk texts for prompt
    for h in hits:
        p = h.get("payload", {})
        p["text"] = sanitize_context(p.get("text",""))
        h["payload"] = p

    suspicious = any_context_is_suspicious([h.get("payload",{}).get("text","") for h in hits])

    # Pass embed_model to hits for relevance computation
    if settings.use_relevance_gate:
        for h in hits:
            h["embed_model"] = embed_model
    
    # Answerability gate with relevance checking
    can_answer, reason = check_answerability(
        hits, 
        query=question,
        score_threshold=settings.score_threshold,
        relevance_threshold=settings.relevance_threshold,
        min_relevant_sources=settings.min_relevant_sources,
        use_relevance_gate=settings.use_relevance_gate,
    )
    
    # Log relevance scores for debugging
    if settings.use_relevance_gate:
        for h in hits:
            rel = h.get("query_relevance", None)
            if rel is not None:
                logger.info(f"Source relevance: {rel:.3f} - {h.get('payload', {}).get('title', 'Unknown')[:50]}")
    if not can_answer:
        # Generate clarifying questions based on retrieved sources
        source_topics = []
        for h in hits[:3]:  # Look at top 3 sources
            title = h.get("payload", {}).get("title", "")
            if title:
                # Extract key topics from title (simple heuristic)
                words = title.lower().split()
                # Filter common words
                stop_words = {"ja", "on", "oli", "tapahtui", "uutinen", "artikkeli", "the", "a", "an", "and", "or"}
                topics = [w for w in words if len(w) > 3 and w not in stop_words][:2]
                source_topics.extend(topics)
        
        # Create clarifying questions
        if "relevant" in reason.lower() or "clarify" in reason.lower():
            clarifying = [
                "Voitko tarkentaa, mistä aiheesta haluat tietää?",
                "Haluatko tietää jotain tietystä tapahtumasta vai yleisestä aiheesta?",
            ]
            if source_topics:
                clarifying.append(f"Löytyneet lähteet käsittelevät aiheita kuten: {', '.join(set(source_topics[:3]))}. Haluatko tietää näistä?")
        else:
            clarifying = [
                "Tarvitsen lisää lähteitä vastatakseni tähän kysymykseen.",
                "Voitko muotoilla kysymyksen toisin tai tarkentaa, mitä haluat tietää?",
            ]
        
        answer = (
            f"En voi vastata luotettavasti nykyisten lähteiden perusteella.\n\n"
            f"{reason}\n\n"
            f"Selventäviä kysymyksiä:\n"
            + "\n".join(f"- {q}" for q in clarifying)
        )
        warnings = [reason]
        # Determine which model was actually used
        if settings.llm_provider.lower() == "ollama":
            model_name = settings.ollama_model
        elif settings.llm_provider.lower() == "vllm":
            model_name = settings.vllm_model
        elif settings.llm_provider.lower() == "mistral":
            model_name = settings.mistral_model
        else:
            model_name = settings.vllm_model  # Default fallback
        
        run = ChatRun(
            question=question,
            answer=answer,
            model=model_name,
            embed_model=settings.embed_model,
            rerank_model=settings.rerank_model if settings.use_rerank else None,
            top_k=settings.top_k,
            mmr_k=settings.mmr_k,
            score_threshold=settings.score_threshold,
            suspicious_context=False,
        )
        saved = save_run(engine, run, [])
        return ChatResponse(
            answer=answer,
            sources=[],
            hits=[],
            run_id=saved.id,  # type: ignore
            warnings=warnings,
        )

    hits_labeled, sources = assign_source_labels(hits)
    
    # For latest intent, ensure we only have S1
    if query_intent.intent == "latest" and len(sources) > 1:
        # Keep only the first source (newest)
        sources = sources[:1]
        # Update hits_labeled to match
        hits_labeled = [h for h in hits_labeled if h.get("source_label") == "S1"]
        logger.info(f"Latest intent: limiting to single source S1")
    
    prompt = build_cited_prompt(question, hits_labeled, sources)

    llm = _llm()
    warnings: List[str] = []
    sources_used: List[str] = []  # Track which sources were actually used
    
    try:
        answer_raw = llm.generate(prompt, max_tokens=settings.max_answer_tokens)
        
        # Try to parse JSON output
        answer, sources_used_json = _parse_structured_output(answer_raw, sources)
        
        # If JSON parsing failed, fall back to plain text
        if not answer:
            answer = answer_raw
            # Clean up obvious repetitions
            answer = _remove_repetitions(answer)
            # Remove prompt leakage
            answer = _remove_prompt_leakage(answer)
            
            # If answer still contains instruction markers, re-generate with stricter prompt
            if _has_instruction_leakage(answer):
                logger.warning("Detected instruction leakage, re-generating with stricter prompt")
                # Build context string for strict prompt
                ctx_lines = []
                for h in hits_labeled:
                    p = h.get("payload", {}) if "payload" in h else h
                    label = h.get("source_label", "S?")
                    chunk = p.get("text") or ""
                    title = p.get("title") or ""
                    ctx_lines.append(f"{label} {title}: {chunk}")
                ctx_str = "\n\n".join(ctx_lines)
                
                available_labels = ', '.join([s.label for s in sources])
                strict_prompt = f"""Vastaa kysymykseen suomeksi käyttäen vain annettua kontekstia.

Kysymys: {question}

Konteksti:
{ctx_str}

Lähteet (käytä vain näitä): {available_labels}

Vastaa suomeksi. Jokainen faktaväite tarvitsee lähdeviitteen muodossa (S1), (S2) jne. Lopussa otsikko "Lähteet:" ja listaa käyttämäsi lähteet."""
                answer_raw2 = llm.generate(strict_prompt, max_tokens=settings.max_answer_tokens)
                answer, sources_used_json = _parse_structured_output(answer_raw2, sources)
                if not answer:
                    answer = answer_raw2
                    answer = _remove_repetitions(answer)
                    answer = _remove_prompt_leakage(answer)
        else:
            # JSON parsing succeeded - validate sources_used
            sources_used = sources_used_json
            available_labels = {s.label for s in sources}
            invalid_sources = set(sources_used) - available_labels
            if invalid_sources:
                warnings.append(f"Model cited non-existent sources: {invalid_sources}")
                # Filter out invalid sources
                sources_used = [s for s in sources_used if s in available_labels]
        
        err = None
        
        # Remove any bracket citations [S1] from answer - they're not valid
        answer = _remove_bracket_citations(answer, sources)
        
        # Validate citations: ensure no non-existent sources are cited
        answer = _validate_citations(answer, sources, warnings)
        
        # If JSON format was used, don't add Sources section (UI will show it)
        # Only add Sources section if answer is plain text format
        if not sources_used:
            # Plain text format - ensure Sources section exists
            answer = _ensure_sources_section(answer, sources, sources_used=None)
        # If sources_used exists, JSON format was used - don't add Sources section
        
        # Citation coverage check with hard enforcement
        has_coverage, coverage_warnings = check_citation_coverage(answer, sources)
        if not has_coverage:
            # Check if answer has any citations at all - ONLY parentheses format (S1)
            # Ignore bracket format [S1] - it's not a valid citation
            import re
            has_any_citations = bool(re.search(r'\(S\d+\)', answer))
            
            if not has_any_citations and len(sources) > 0:
                # No citations at all - this is a critical failure
                # Refuse to answer rather than show uncited content
                answer = (
                    f"En voi vastata luotettavasti, koska vastaus ei sisältänyt lähdeviitteitä. "
                    f"Tarvitsen vastauksen, jossa jokainen faktaväite viittaa lähteeseen [S1], [S2], jne. "
                    f"Pyydä uudelleen tai tarkenna kysymystäsi."
                )
                warnings.append("Answer generated without citations - refused to display")
            else:
                # Try to add missing citations automatically FIRST
                answer_before_fix = answer
                answer = _add_missing_citations(answer, sources, warnings)
                
                # Re-check after auto-fix
                if answer != answer_before_fix:
                    has_coverage_after, coverage_warnings_after = check_citation_coverage(answer, sources)
                    if has_coverage_after:
                        # Auto-fix worked, clear critical warnings
                        coverage_warnings = [w for w in coverage_warnings_after if "CRITICAL" not in w]
                    else:
                        # Still has issues, but less severe
                        coverage_warnings = coverage_warnings_after
                
                warnings.extend(coverage_warnings)
    except Exception as e:
        answer = "Virhe LLM-kutsussa."
        err = str(e)
        warnings.append(f"LLM error: {str(e)}")

    latency_ms = (time.time() - start_time) * 1000
    
    # Determine which model was actually used
    if settings.llm_provider.lower() == "ollama":
        model_name = settings.ollama_model
    elif settings.llm_provider.lower() == "vllm":
        model_name = settings.vllm_model
    elif settings.llm_provider.lower() == "mistral":
        model_name = settings.mistral_model
    else:
        model_name = settings.vllm_model  # Default fallback
    
    run = ChatRun(
        question=question,
        answer=answer,
        model=model_name,
        embed_model=settings.embed_model,
        rerank_model=settings.rerank_model if settings.use_rerank else None,
        prompt_version="v1",
        top_k=settings.top_k,
        mmr_k=settings.mmr_k,
        score_threshold=settings.score_threshold,
        retrieval_params={
            "use_bm25": settings.use_bm25,
            "bm25_weight": settings.bm25_weight,
        },
        suspicious_context=suspicious,
        error=err,
        warnings=warnings,
        latency_ms=latency_ms,
    )

    # Determine which sources to return (only those cited if JSON format, all if plain text)
    if sources_used:
        # Only include sources that were cited in the answer
        selected_sources = [s for s in sources if s.label in sources_used]
        logger.info(f"Returning {len(selected_sources)} selected sources (from {len(sources)} total, {len(sources_used)} cited)")
    else:
        # Plain text format - return all sources passed to LLM
        selected_sources = sources
    
    # Only include hits that correspond to selected sources
    selected_source_labels = {s.label for s in selected_sources}
    selected_hits_labeled = [h for h in hits_labeled if h.get("source_label") in selected_source_labels]
    
    hit_rows = []
    hit_items = []
    for h in selected_hits_labeled:
        p = h.get("payload", {})
        hit_rows.append(RetrievalHit(
            uid=p.get("uid"),
            source_label=h.get("source_label"),
            source_id=p.get("source_id") or p.get("source"),
            title=p.get("title"),
            url=p.get("url"),
            published_at=p.get("published_at"),
            score=h.get("score"),
            rerank_score=h.get("rerank_score"),
            text_snippet=(p.get("text") or "")[:240],
        ))
        hit_items.append(HitItem(
            uid=p.get("uid"),
            source_label=h.get("source_label"),
            title=p.get("title"),
            url=p.get("url"),
            published_at=p.get("published_at"),
            score=h.get("score"),
            rerank_score=h.get("rerank_score"),
            text=p.get("text"),
        ))

    saved = save_run(engine, run, hit_rows)

    src_items = [SourceItem(label=s.label, title=s.title, url=s.url, published_at=s.published_at, publisher=s.publisher) for s in selected_sources]

    if suspicious:
        warnings.append("Suspicious content detected in retrieved sources")

    return ChatResponse(
        answer=answer,
        sources=src_items,  # Only selected sources
        hits=hit_items,  # Only selected hits
        run_id=saved.id,  # type: ignore
        warnings=warnings,
    )

@app.get("/runs", response_model=list[RunItem])
def runs(limit: int = 20):
    rs = list_runs(engine, limit=limit)
    return [RunItem(id=r.id, created_at=r.created_at.isoformat(), question=r.question, model=r.model) for r in rs if r.id is not None]

@app.get("/runs/{run_id}")
def run_detail(run_id: int):
    r = read_run(engine, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="not found")
    return r

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "transparent-news-assistant"}

@app.get("/ready")
def ready():
    """Readiness check endpoint."""
    try:
        # Check Qdrant connection
        qdrant.get_collections()
        # Check DB connection
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        logger.error("readiness_check_failed", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail=f"Not ready: {str(e)}")

@app.delete("/articles", response_model=DeleteArticleResponse)
def delete_article(req: DeleteArticleRequest):
    """Delete all chunks for an article by URL or article_id."""
    if not req.url and not req.article_id:
        raise HTTPException(status_code=400, detail="Either url or article_id required")
    
    if req.url:
        n = delete_article_by_url(qdrant, settings.qdrant_collection, req.url)
    else:
        n = delete_article_by_id(qdrant, settings.qdrant_collection, req.article_id)  # type: ignore
    
    return DeleteArticleResponse(deleted_chunks=n)
