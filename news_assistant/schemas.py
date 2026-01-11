from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class IngestRequest(BaseModel):
    feed_url: str
    publisher: Optional[str] = None
    limit: int = 30


class IngestResponse(BaseModel):
    indexed_chunks: int


class ChatRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    label: str
    title: str
    url: Optional[str] = None
    published_at: Optional[str] = None
    publisher: Optional[str] = None


class HitItem(BaseModel):
    uid: Optional[str] = None
    source_label: str
    title: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None
    score: Optional[float] = None
    rerank_score: Optional[float] = None
    text: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    hits: List[HitItem]
    run_id: int
    warnings: List[str] = []


class RunItem(BaseModel):
    id: int
    created_at: str
    question: str
    model: str


class DeleteArticleRequest(BaseModel):
    url: str | None = None
    article_id: str | None = None


class DeleteArticleResponse(BaseModel):
    deleted_chunks: int
