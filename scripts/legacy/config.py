"""
Configuration constants for the RAG pipeline.

This module contains all configuration settings including:
- Collection names
- Model names
- Feature flags
- Demo documents
"""

COLLECTION = "demo_docs"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Feature flags
RESET = False             # True -> nollaa kokoelman kerran ennen luontia
DEDUPE_BY_SOURCE = False  # True -> max 1 katkelma per lähde (polku/x)

# Demo documents
DOCS = [
    {"id": "polku/1", "title": "Qdrant pähkinänkuoressa",
     "text": "Qdrant on vektoritietokanta, joka tukee HNSW-indeksointia, metadatafilttereitä ja reaaliaikaisia päivityksiä."},
    {"id": "polku/2", "title": "RAG-perusteet",
     "text": "RAG yhdistää haun ja generoinnin: dokumentit pilkotaan, indeksoidaan vektorimuotoon ja haetaan semanttisesti."},
    {"id": "polku/3", "title": "Embeddings lyhyesti",
     "text": "Upotteet (embeddings) kuvaavat tekstin merkityssisältöä, mahdollistaen samankaltaisuushakuja kosinietäisyydellä."},
]
