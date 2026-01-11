"""Ingestion adapters for various news sources."""
from .base import Article, Ingestor, IngestResult
from .rss import RSSIngestor
from .yle import YleIngestor

__all__ = ["Article", "Ingestor", "IngestResult", "RSSIngestor", "YleIngestor"]
