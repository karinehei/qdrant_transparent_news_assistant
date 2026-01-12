"""
Prompting Module

Handles prompt construction for LLM integration.
"""

from typing import List, Dict


def format_contexts(contexts: List[Dict]) -> str:
    """
    Format retrieved contexts into a readable string for prompt construction.
    
    Args:
        contexts: List of context dictionaries with 'source', 'title', 'text', 'score'
    
    Returns:
        Formatted string with contexts separated by delimiters, or empty string if no contexts
    """
    if not contexts:
        return ""
    lines = []
    for c in contexts:
        src = c.get("source", "tuntematon")
        title = c.get("title", "—")
        score = c.get("score")
        score_s = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
        text = c.get("text", "")
        lines.append(f"[lähde: {src}] {title} (osuma: {score_s})\n{text}")
    return "\n\n---\n\n".join(lines)


def build_prompt(question: str, contexts: List[Dict]) -> str:
    """
    Build a prompt for LLM with question and retrieved contexts.
    
    Creates a Finnish-language prompt that instructs the LLM to:
    - Answer using only the provided context
    - Use Finnish terminology (e.g., "vektoritietokanta" instead of "vector database")
    - Avoid repetition and tautologies
    - Include source citations
    
    Args:
        question: User's question
        contexts: List of retrieved context dictionaries
    
    Returns:
        Complete prompt string ready for LLM input
    
    Note:
        Prompt is optimized for Finnish language responses. Modify for other languages.
    """
    ctx = format_contexts(contexts)
    return f"""Vastaa suomeksi käyttäen termiä "vektoritietokanta".
Hyödynnä VAIN alla olevaa kontekstia. Jos konteksti puuttuu, vastaa täsmälleen: "en tiedä" ja pyydä lisää lähteitä.
Älä lisää ulkopuolisia linkkejä. Vältä toistoa ja tautologioita (esim. "hakuun perustuva haku"); vältä anglismeja ("embed") ja käytä "upote"/"upottaa".

KYSYMYS:
{question}

KONTEKSTI:
{ctx}

OHJEET VASTAUKSEEN:
- Anna 3–4 napakkaa bullet-kohtaa (ei pitkiä kappaleita) vain jos kontekstia on.
- Käsittele mieluiten: semanttinen haku, HNSW/nopeus, metadatafiltterit, reaaliaikaiset päivitykset.
- Pysy kontekstissa; älä keksi uutta.
- **Lopeta aina otsikolla 'Lähteet:' ja listaa käytetyt polut muodossa [lähde: POLKU].**
"""
