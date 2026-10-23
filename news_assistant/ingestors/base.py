"""Base classes for ingestion adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Article:
    """Normalized article representation."""

    url: str
    title: str
    text: str
    published_at: str | None = None  # ISO format string
    publisher: str | None = None
    language: str | None = None
    tags: list[str] | None = None
    section: str | None = None
    source_id: str | None = None  # Internal ID from source


@dataclass
class IngestResult:
    """Result of an ingestion run."""

    articles: list[Article]
    count_ingested: int
    errors: list[str]
    source_type: str
    source_ref: str  # Feed URL, API endpoint, etc.


class Ingestor(ABC):
    """Base interface for ingestion adapters."""

    @abstractmethod
    def fetch_articles(
        self,
        source_ref: str,
        publisher: str | None = None,
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
