from __future__ import annotations

from pydantic import BaseModel


class IngestRequest(BaseModel):
    feed_url: str
    publisher: str | None = None
    limit: int = 30


class IngestResponse(BaseModel):
    indexed_chunks: int


class ChatRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    label: str
    title: str
    url: str | None = None
    published_at: str | None = None
    publisher: str | None = None


class HitItem(BaseModel):
    uid: str | None = None
    source_label: str
    title: str | None = None
    url: str | None = None
    published_at: str | None = None
    score: float | None = None
    rerank_score: float | None = None
    text: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    hits: list[HitItem]
    run_id: int
    warnings: list[str] = []


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
