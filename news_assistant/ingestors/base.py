"""Base classes for ingestion adapters."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Article:
    """Normalized article representation."""
    url: str
    title: str
    text: str
    published_at: Optional[str] = None  # ISO format string
    publisher: Optional[str] = None
    language: Optional[str] = None
    tags: Optional[List[str]] = None
    section: Optional[str] = None
    source_id: Optional[str] = None  # Internal ID from source


@dataclass
class IngestResult:
    """Result of an ingestion run."""
    articles: List[Article]
    count_ingested: int
    errors: List[str]
    source_type: str
    source_ref: str  # Feed URL, API endpoint, etc.


class Ingestor(ABC):
    """Base interface for ingestion adapters."""
    
    @abstractmethod
    def fetch_articles(
        self,
        source_ref: str,
        publisher: Optional[str] = None,
        limit: int = 30,
    ) -> IngestResult:
        """
        Fetch articles from a source.
        
        Args:
            source_ref: Source identifier (URL, API endpoint, etc.)
            publisher: Optional publisher name to override
            limit: Maximum number of articles to fetch
            
        Returns:
            IngestResult with articles and metadata
        """
        pass
