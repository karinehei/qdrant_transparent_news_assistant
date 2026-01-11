from __future__ import annotations
from typing import List, Dict
import feedparser
import requests
from bs4 import BeautifulSoup


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # remove scripts/styles
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = soup.get_text(" ", strip=True)
    return text


def fetch_rss(feed_url: str, publisher: str | None = None, limit: int = 30) -> List[Dict]:
    d = feedparser.parse(feed_url)
    out: List[Dict] = []
    for e in d.entries[:limit]:
        url = getattr(e, "link", None)
        title = getattr(e, "title", "") or ""
        published = getattr(e, "published", None) or getattr(e, "updated", None)
        published_at = None
        if published:
            published_at = published  # keep as string for simplicity
        # text: prefer content/summary
        text = ""
        if hasattr(e, "content") and e.content:
            text = e.content[0].value
        elif hasattr(e, "summary"):
            text = e.summary
        # try fetch full page (best-effort)
        if url:
            try:
                r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                if r.ok and r.text:
                    page_text = _clean_html(r.text)
                    # only replace if significantly longer
                    if len(page_text) > len(text) + 300:
                        text = page_text
            except Exception:
                pass
        text = _clean_html(text) if "<" in text else text
        out.append(
            {
                "id": url or title,
                "url": url,
                "title": title,
                "text": text.strip(),
                "published_at": published_at,
                "publisher": publisher,
            }
        )
    return [a for a in out if a.get("text")]
