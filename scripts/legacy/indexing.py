"""
Indexing Module

Handles Qdrant collection management and document indexing.
"""

from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import uuid
from config import COLLECTION, RESET


def ensure_collection(client: QdrantClient, dim: int):
    """
    Ensure Qdrant collection exists, creating it if necessary.
    
    If RESET flag is True, deletes existing collection before creating.
    Collection uses COSINE distance metric for vector similarity.
    
    Args:
        client: QdrantClient instance connected to Qdrant server
        dim: Vector dimension size (must match embedding model output)
    
    Note:
        Set RESET=True to delete and recreate collection. Set to False
        after first run to preserve existing data.
    """
    # Kerran nollaus: aseta RESET=True ja aja; palaa False:ksi seuraavilla ajoilla
    if RESET and client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def index(client: QdrantClient, model: SentenceTransformer, corpus: List[Dict]):
    """
    Index corpus into Qdrant collection.
    
    Generates embeddings for all corpus texts, creates point structures
    with deterministic UUIDs based on UID, and upserts them to Qdrant.
    
    Args:
        client: QdrantClient instance
        model: SentenceTransformer model for generating embeddings
        corpus: List of corpus entries with 'text', 'uid', 'title', 'source' keys
    
    Note:
        Uses uuid5 with NAMESPACE_URL to generate deterministic UUIDs from UIDs.
        This ensures same UID always maps to same UUID, enabling idempotent indexing.
    """
    vectors = model.encode([c["text"] for c in corpus], normalize_embeddings=True).tolist()
    points = []
    for v, c in zip(vectors, corpus):
        pid = uuid.uuid5(uuid.NAMESPACE_URL, c["uid"])  # sama uid -> sama UUID
        points.append(
            PointStruct(
                id=str(pid),
                vector=v,
                payload={"uid": c["uid"], "title": c["title"], "text": c["text"], "source": c["source"]},
            )
        )
    client.upsert(collection_name=COLLECTION, points=points)
