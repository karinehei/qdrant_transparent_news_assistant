from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
import re

@dataclass
class SourceRef:
    key: str
    label: str   # e.g. S1
    title: str
    url: str | None
    published_at: str | None
    publisher: str | None

def assign_source_labels(hits: List[Dict]) -> Tuple[List[Dict], List[SourceRef]]:
    """Assign stable labels [S1], [S2] ... to unique sources inside hits.
    Expects each hit payload to include: source_id (or source), title, url (optional), published_at (optional), publisher(optional).
    """
    sources: Dict[str, SourceRef] = {}
    ordered: List[str] = []
    for h in hits:
        p = h.get("payload", {}) if "payload" in h else h
        key = p.get("source_id") or p.get("source") or p.get("url") or p.get("uid") or "unknown"
        if key not in sources:
            ordered.append(key)
            sources[key] = SourceRef(
                key=key,
                label=f"S{len(ordered)}",
                title=p.get("title") or "Untitled",
                url=p.get("url"),
                published_at=p.get("published_at"),
                publisher=p.get("publisher"),
            )
    # annotate hits
    out_hits = []
    for h in hits:
        p = h.get("payload", {}) if "payload" in h else h
        key = p.get("source_id") or p.get("source") or p.get("url") or p.get("uid") or "unknown"
        sr = sources[key]
        new = dict(h)
        new["source_label"] = sr.label
        out_hits.append(new)
    return out_hits, [sources[k] for k in ordered]

def compute_query_relevance(
    query: str, 
    hit_text: str, 
    hit_title: str = "",
    embed_model=None,
    vector_score: float = None
) -> float:
    """
    Compute relevance score between query and a hit.
    Uses embedding similarity if embed_model provided, otherwise falls back to token overlap.
    
    Args:
        query: User query
        hit_text: Document text
        hit_title: Document title
        embed_model: Optional SentenceTransformer model for semantic similarity
        vector_score: Optional pre-computed vector similarity score from retrieval
    
    Returns:
        Relevance score between 0.0 and 1.0
    """
    import re
    import numpy as np
    
    # If we have vector_score from retrieval, use it as primary signal (it's already semantic)
    # Vector scores are cosine similarity, typically 0.0-1.0, but can be negative
    if vector_score is not None and vector_score > 0:
        # Normalize vector score to 0-1 range (assuming typical range is 0.2-0.9)
        # Map [0.2, 0.9] -> [0.0, 1.0] for better threshold matching
        normalized_vector = max(0.0, min(1.0, (vector_score - 0.2) / 0.7)) if vector_score > 0.2 else vector_score / 0.2
        vector_weight = 0.6  # Primary signal
    else:
        normalized_vector = 0.0
        vector_weight = 0.0
    
    # Use embedding model for semantic similarity if available
    if embed_model is not None:
        try:
            query_vec = embed_model.encode([query], normalize_embeddings=True)[0]
            doc_text = (hit_title + " " + hit_text)[:500]  # Limit length for efficiency
            doc_vec = embed_model.encode([doc_text], normalize_embeddings=True)[0]
            
            # Cosine similarity
            semantic_score = float(np.dot(query_vec, doc_vec))
            
            # Normalize to 0-1 range (cosine similarity is typically -1 to 1, but normalized embeddings give 0-1)
            semantic_score = max(0.0, min(1.0, semantic_score))
            
            if vector_weight > 0:
                # Combine vector score (from retrieval) with fresh semantic score
                relevance = vector_weight * normalized_vector + (1 - vector_weight) * semantic_score
            else:
                relevance = semantic_score
            
            return relevance
        except Exception:
            # Fall through to token-based if embedding fails
            pass
    
    # Fallback: Token overlap (Jaccard similarity)
    query_tokens = set(re.findall(r'\w+', query.lower()))
    text_lower = (hit_text + " " + hit_title).lower()
    title_lower = hit_title.lower()
    text_tokens = set(re.findall(r'\w+', text_lower))
    title_tokens = set(re.findall(r'\w+', title_lower))
    
    if not query_tokens:
        return 0.0
    
    # Direct token overlap
    overlap = len(query_tokens & text_tokens)
    title_overlap = len(query_tokens & title_tokens)
    union = len(query_tokens | text_tokens)
    
    if union == 0:
        return 0.0
    
    jaccard = overlap / union
    
    # Boost if query tokens appear multiple times
    token_counts = sum(text_lower.count(token) for token in query_tokens)
    tf_boost = min(1.0, token_counts / (len(query_tokens) * 2))
    
    # Title matches are very important - give high boost
    title_boost = (title_overlap / len(query_tokens)) * 0.5 if query_tokens else 0.0
    
    # Calculate base relevance with multiple signals
    base_relevance = 0.5 * jaccard + 0.3 * tf_boost + 0.2 * title_boost
    
    # If we have significant overlap (especially in title), boost more
    if title_overlap >= len(query_tokens) * 0.5:  # At least half of query tokens in title
        base_relevance = max(base_relevance, 0.5)
    elif overlap > 0:
        # If any tokens match, ensure minimum relevance based on match ratio
        match_ratio = overlap / len(query_tokens)
        base_relevance = max(base_relevance, 0.2 + (match_ratio * 0.3))  # 0.2 to 0.5 range

    token_relevance = min(1.0, base_relevance)  # Cap at 1.0
    
    # If we have vector score, combine it with token relevance
    if vector_weight > 0:
        return vector_weight * normalized_vector + (1 - vector_weight) * token_relevance
    
    return min(1.0, token_relevance)


def check_answerability(
    hits: List[Dict], 
    query: str,
    score_threshold: float = 0.3,
    relevance_threshold: float = 0.35,
    min_relevant_sources: int = 1,
    use_relevance_gate: bool = True,
) -> tuple[bool, str]:
    """
    Check if we have enough relevant sources to answer the question.
    Now includes query-to-source relevance validation.
    
    Args:
        hits: Retrieved hits
        query: User's question
        score_threshold: Minimum vector similarity score
        relevance_threshold: Minimum query-to-source relevance (0.0-1.0)
        min_relevant_sources: Minimum number of sources above relevance threshold
        use_relevance_gate: Whether to enforce relevance checking
    
    Returns:
        (can_answer, reason)
    """
    if not hits:
        return False, "No sources retrieved"
    
    # Check if any hit has reasonable vector similarity score
    max_score = max((h.get("score", 0.0) for h in hits), default=0.0)
    if max_score < score_threshold:
        return False, f"Retrieval confidence too low (max score: {max_score:.2f} < {score_threshold})"
    
    # Check query-to-source relevance if enabled
    if use_relevance_gate and query:
        relevant_sources = []
        # Get embed_model from hits if available (passed from API)
        embed_model = None
        for h in hits:
            if "embed_model" in h:
                embed_model = h["embed_model"]
                break
        
        for h in hits:
            payload = h.get("payload", {})
            text = payload.get("text", "")
            title = payload.get("title", "")
            vector_score = h.get("score")  # Use vector similarity from retrieval
            
            relevance = compute_query_relevance(
                query, 
                text, 
                title,
                embed_model=embed_model,
                vector_score=vector_score
            )
            h["query_relevance"] = relevance  # Store for logging
            
            if relevance >= relevance_threshold:
                relevant_sources.append((h, relevance))
        
        if len(relevant_sources) < min_relevant_sources:
            max_relevance = max((r for _, r in relevant_sources), default=0.0) if relevant_sources else 0.0
            return False, (
                f"Insufficient relevant sources. "
                f"Found {len(relevant_sources)}/{len(hits)} sources above relevance threshold {relevance_threshold:.2f}. "
                f"Max relevance: {max_relevance:.2f}. "
                f"Please clarify your question or ask about topics covered in the available sources."
            )
    
    # Check if we have enough content
    total_text = sum(len(h.get("payload", {}).get("text", "")) for h in hits)
    if total_text < 200:
        return False, f"Insufficient content (total: {total_text} chars)"
    
    return True, ""


def check_citation_coverage(answer: str, sources: List[SourceRef]) -> tuple[bool, List[str]]:
    """
    Strictly check if answer has citations for factual claims.
    This is a hard requirement - answers without proper citations are considered invalid.
    
    Returns:
        (has_coverage, warnings)
    """
    warnings = []
    
    # Extract source labels from answer - ONLY parentheses format (S1)
    # Bracket format [S1] is completely ignored - not treated as citations at all
    # This ensures [S2], [S3] etc. are completely ignored and never reported as invalid
    cited_with_parens = set(re.findall(r'\(S\d+\)', answer))
    cited_labels = {label.strip('()') for label in cited_with_parens}
    
    # Note: bracket citations [S1] are intentionally ignored - they're not valid citation format
    
    available_labels = {s.label for s in sources}
    
    # CRITICAL: Check for citations to non-existent sources (hard error)
    # Only check parentheses citations - brackets are ignored
    invalid_citations = cited_labels - available_labels
    if invalid_citations:
        invalid_formatted = {f"({label})" for label in invalid_citations}
        warnings.append(f"CRITICAL: Answer cites non-existent sources: {invalid_formatted}")
    
    # Check for uncited factual statements (strict check)
    # Split into sentences more carefully
    sentences = re.split(r'([.!?]+)\s+', answer)
    # Recombine sentences with their punctuation
    sentence_pairs = []
    for i in range(0, len(sentences) - 1, 2):
        if i + 1 < len(sentences):
            sentence_pairs.append(sentences[i] + sentences[i + 1])
        else:
            sentence_pairs.append(sentences[i])
    
    factual_indicators = [
        "on",
        "oli",
        "tapahtui",
        "sanoi",
        "kertoi",
        "mukaan",
        "vuonna",
        "vuosina",
        "is",
        "was",
        "happened",
        "said",
        "according",
        "year",
        "percent",
        "%",
        "tapahtui",
        "syntyi",
        "kuoli",
        "perustettiin",
        "julkaistiin",
    ]
    
    uncited_sentences = []
    for sent in sentence_pairs:
        sent_clean = sent.strip()
        if not sent_clean or len(sent_clean) < 10:  # Skip very short fragments
            continue
        sent_lower = sent_clean.lower()
        
        # Skip if it's just "Lähteet:" or similar
        if sent_lower.startswith("lähteet:") or sent_lower.startswith("sources:"):
            continue
        
        # Check if sentence looks factual
        if any(ind in sent_lower for ind in factual_indicators):
            # Check if it has a citation - ONLY parentheses format (S1)
            # Bracket format [S1] is ignored - not valid citations
            if not re.search(r'\(S\d+\)', sent_clean):
                uncited_sentences.append(sent_clean[:150])  # Truncate for warning
    
    if uncited_sentences:
        # Count how many sentences are uncited vs total factual sentences
        total_factual = len([s for s in sentence_pairs if any(ind in s.lower() for ind in factual_indicators)])
        uncited_ratio = len(uncited_sentences) / max(total_factual, 1)
        
        # Only mark as CRITICAL if most statements are uncited (>70%)
        # For 50-70%, it's a warning but not critical
        # For <50%, it's minor and can be auto-fixed
        if uncited_ratio > 0.7:  # More than 70% uncited - critical
            warnings.append(
                f"CRITICAL: {len(uncited_sentences)}/{total_factual} factual statements lack citations. "
                f"Answer may be unreliable."
            )
        elif uncited_ratio > 0.5:  # 50-70% uncited - significant warning
            warnings.append(
                f"Warning: {len(uncited_sentences)}/{total_factual} factual statements lack citations. "
                f"Consider adding citations for better reliability."
            )
        elif len(uncited_sentences) <= 2:  # 1-2 uncited sentences - minor, can be auto-fixed
            # Don't warn for very minor omissions (1-2 sentences)
            pass
        else:  # 3+ uncited but <50% - moderate warning
            warnings.append(f"Found {len(uncited_sentences)} potentially uncited factual statements")
    
    # Check if answer mentions sources section (now handled by _ensure_sources_section, but warn if missing)
    if "lähteet:" not in answer.lower() and "sources:" not in answer.lower():
        warnings.append("Answer missing Sources section (will be auto-added)")
    
    has_coverage = len([w for w in warnings if "CRITICAL" in w]) == 0
    return has_coverage, warnings


def build_cited_prompt(question: str, hits: List[Dict], sources: List[SourceRef]) -> str:
    ctx_lines = []
    for i, h in enumerate(hits, start=1):
        p = h.get("payload", {}) if "payload" in h else h
        label = h.get("source_label", "S?")
        chunk = p.get("text") or ""
        title = p.get("title") or ""
        ctx_lines.append(f"[{label}] {title}: {chunk}")
    ctx = "\n\n".join(ctx_lines)

    src_lines = []
    for s in sources:
        bits = []
        if s.publisher:
            bits.append(s.publisher)
        if s.published_at:
            bits.append(s.published_at)
        meta = " — ".join(bits) if bits else ""
        url = s.url or s.key
        src_lines.append(f"[{s.label}] {s.title} — {url}{(' — ' + meta) if meta else ''}")

    sources_block = "\n".join(src_lines)

    # Build available source labels for validation
    available_labels = [s.label for s in sources]
    sources_list = ", ".join(available_labels)
    
    return f"""Sinä olet uutisavustaja. Vastaa kysymykseen käyttäen vain annettua kontekstia.

Säännöt:
- Käytä vain kontekstissa olevaa tietoa. Älä keksi mitään.
- Jos konteksti ei vastaa kysymykseen, sano: "Kontekstista ei löydy tietoa tästä aiheesta."
- Jokainen faktaväite tarvitsee lähdeviitteen muodossa (S1), (S2), jne.
- Voit käyttää vain näitä lähteitä: {sources_list}
- ÄLÄ lisää "Lähteet:" osiota vastaukseen - se lisätään automaattisesti.

Kysymys:
{question}

Konteksti:
{ctx}

Lähteet:
{sources_block}

Vastaa suomeksi selkeästi. Jokainen faktaväite tarvitsee lähdeviitteen. Älä toista näitä ohjeita vastauksessa.

Palauta vastaus JSON-muodossa (VAIN JSON, ei tekstiä ennen tai jälkeen):
{{
  "answer_fi": ["bullet 1 (S1)", "bullet 2 (S2)", ...],
  "sources_used": ["S1", "S2", ...]
}}
"""
