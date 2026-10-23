"""Yle API ingestor (scaffold with mock mode)."""

from __future__ import annotations

import logging
import os

import requests

from .base import Article, Ingestor, IngestResult

logger = logging.getLogger(__name__)

# Yle API base URL
YLE_API_BASE = "https://external.api.yle.fi/v1"


class YleIngestor(Ingestor):
    """Yle API ingestor with mock mode for development."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize Yle ingestor.

        Args:
            api_key: Yle API key. If None, will try YLE_API_KEY env var.
                     If still None, runs in mock mode.
        """
        self.api_key = api_key or os.getenv("YLE_API_KEY")
        self.mock_mode = self.api_key is None

    def fetch_articles(
        self,
        source_ref: str,
        publisher: str | None = "Yle",
        limit: int = 30,
    ) -> IngestResult:
        """
        Fetch articles from Yle API.

        Args:
            source_ref: API endpoint path (e.g., "/articles/list") or query params
            publisher: Publisher name (default: "Yle")
            limit: Maximum articles to fetch

        Returns:
            IngestResult with articles and metadata
        """
        errors: list[str] = []
        articles: list[Article] = []

        if self.mock_mode:
            logger.warning("YleIngestor running in mock mode (no API key). Returning sample data.")
            # Return mock articles for development
            articles = [
                Article(
                    url="https://yle.fi/a/123456",
                    title="Mock Yle Article 1",
                    text="This is a mock article for development. To use real Yle API, set YLE_API_KEY environment variable.",
                    published_at="2024-01-01T12:00:00",
                    publisher="Yle",
                    language="fi",
                    source_id="mock-1",
                ),
                Article(
                    url="https://yle.fi/a/123457",
                    title="Mock Yle Article 2",
                    text="Another mock article. See README for Yle API setup instructions.",
                    published_at="2024-01-01T13:00:00",
                    publisher="Yle",
                    language="fi",
                    source_id="mock-2",
                ),
            ]
            errors.append("Mock mode: Set YLE_API_KEY to use real API")
            return IngestResult(
                articles=articles,
                count_ingested=len(articles),
                errors=errors,
                source_type="yle",
                source_ref=source_ref,
            )

        # Real API implementation
        try:
            # Construct API URL
            # Yle API typically requires app_id and app_key
            # Example: /articles/list?app_id=xxx&app_key=yyy&limit=30
            api_url = f"{YLE_API_BASE}{source_ref}"
            if "?" not in api_url:
                api_url += "?"
            else:
                api_url += "&"
            api_url += f"app_id={self.api_key}&limit={limit}"

            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Parse Yle API response (structure depends on endpoint)
            # This is a scaffold - adjust based on actual Yle API response format
            if "data" in data:
                for item in data["data"][:limit]:
                    try:
                        article = Article(
                            url=item.get("url", ""),
                            title=item.get("headline", {}).get("full", "Untitled"),
                            text=item.get("body", {}).get("text", ""),
                            published_at=item.get("datePublished"),
                            publisher=publisher or "Yle",
                            language=item.get("language", "fi"),
                            source_id=item.get("id"),
                        )
                        if article.text:
                            articles.append(article)
                    except Exception as e:
                        errors.append(f"Error parsing article: {e!s}")

        except requests.exceptions.RequestException as e:
            error_msg = f"Yle API request failed: {e!s}"
            errors.append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Error processing Yle API response: {e!s}"
            errors.append(error_msg)
            logger.exception(error_msg)

        return IngestResult(
            articles=articles,
            count_ingested=len(articles),
            errors=errors,
            source_type="yle",
            source_ref=source_ref,
        )
