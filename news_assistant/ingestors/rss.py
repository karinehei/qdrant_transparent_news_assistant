"""RSS feed ingestor with robust parsing and content extraction."""
from __future__ import annotations
import logging
import time
from typing import List, Optional
import feedparser
import requests
from bs4 import BeautifulSoup

from .base import Article, Ingestor, IngestResult

logger = logging.getLogger(__name__)

# User agent to avoid blocking
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _clean_html(html: str) -> str:
    """Extract clean text from HTML."""
    if not html or not isinstance(html, str):
        return ""
    soup = BeautifulSoup(html, "html.parser")
    # Remove scripts, styles, and other non-content
    for tag in soup(["script", "style", "noscript", "iframe", "meta"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Normalize whitespace
    text = " ".join(text.split())
    return text


def _fetch_full_content(url: str, timeout: int = 10, retries: int = 2) -> Optional[str]:
    """Fetch full article content from URL with retries."""
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True,
            )
            response.raise_for_status()
            if response.text:
                return _clean_html(response.text)
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching {url} (attempt {attempt + 1})")
            if attempt < retries:
                time.sleep(1)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching {url}: {e} (attempt {attempt + 1})")
            if attempt < retries:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            break
    return None


class RSSIngestor(Ingestor):
    """RSS feed ingestor with robust parsing and content extraction."""
    
    def fetch_articles(
        self,
        source_ref: str,
        publisher: Optional[str] = None,
        limit: int = 30,
    ) -> IngestResult:
        """
        Fetch articles from RSS feed.
        
        Args:
            source_ref: RSS feed URL
            publisher: Optional publisher name
            limit: Maximum articles to fetch
            
        Returns:
            IngestResult with articles and metadata
        """
        errors: List[str] = []
        articles: List[Article] = []
        
        try:
            # Parse feed with custom user agent
            feed = feedparser.parse(source_ref)
            
            if feed.bozo and feed.bozo_exception:
                errors.append(f"Feed parse error: {feed.bozo_exception}")
                logger.warning(f"Feed parse warning for {source_ref}: {feed.bozo_exception}")
            
            # Extract publisher from feed if not provided
            if not publisher:
                publisher = getattr(feed.feed, "title", None) or getattr(feed.feed, "link", None)
            
            entries = feed.entries[:limit]
            
            for entry in entries:
                try:
                    url = getattr(entry, "link", None)
                    if not url:
                        errors.append(f"Entry missing URL: {getattr(entry, 'title', 'unknown')}")
                        continue
                    
                    title = getattr(entry, "title", "").strip() or "Untitled"
                    
                    # Extract published date
                    published_at = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            from time import mktime
                            from datetime import datetime
                            dt = datetime.fromtimestamp(mktime(entry.published_parsed))
                            published_at = dt.isoformat()
                        except Exception:
                            pass
                    if not published_at:
                        published_at = getattr(entry, "published", None) or getattr(entry, "updated", None)
                    
                    # Extract text content
                    text = ""
                    if hasattr(entry, "content") and entry.content:
                        text = entry.content[0].value
                    elif hasattr(entry, "summary"):
                        text = entry.summary
                    
                    # Try to fetch full content if summary is short
                    if url and len(text) < 500:
                        full_text = _fetch_full_content(url)
                        if full_text and len(full_text) > len(text) + 300:
                            text = full_text
                    
                    # Clean HTML if present
                    if text and ("<" in text or "&" in text):
                        text = _clean_html(text)
                    
                    text = text.strip()
                    if not text:
                        errors.append(f"Empty content for {url}")
                        continue
                    
                    # Extract tags/section if available
                    tags = None
                    if hasattr(entry, "tags") and entry.tags:
                        tags = [tag.term for tag in entry.tags if hasattr(tag, "term")]
                    
                    section = None
                    if hasattr(entry, "category"):
                        section = entry.category
                    
                    article = Article(
                        url=url,
                        title=title,
                        text=text,
                        published_at=published_at,
                        publisher=publisher,
                        source_id=url,  # Use URL as source_id for RSS
                    )
                    articles.append(article)
                    
                except Exception as e:
                    error_msg = f"Error processing entry: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
        except Exception as e:
            error_msg = f"Failed to fetch RSS feed {source_ref}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return IngestResult(
            articles=articles,
            count_ingested=len(articles),
            errors=errors,
            source_type="rss",
            source_ref=source_ref,
        )
