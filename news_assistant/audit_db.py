from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, create_engine, Session, select, Column
from sqlalchemy import JSON as SQLJSON
# Removed joinedload import - relationships are handled manually for compatibility

class ChatRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # User context (optional, for multi-user scenarios)
    user_id: str | None = None

    question: str
    answer: str

    model: str
    embed_model: str
    rerank_model: str | None = None
    
    # Prompt version for tracking prompt changes
    prompt_version: str = "v1"

    top_k: int
    mmr_k: int
    score_threshold: float
    
    # Store retrieval params as JSON for flexibility
    retrieval_params: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(SQLJSON))

    suspicious_context: bool = False
    error: str | None = None
    
    # Warnings as JSON array
    warnings: List[str] = Field(default_factory=list, sa_column=Column(SQLJSON))
    
    # Latency in milliseconds
    latency_ms: float | None = None

    # Relationship will be defined after both classes are declared

class RetrievalHit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="chatrun.id", index=True)
    
    rank: int | None = None  # Rank in retrieval results (1-based)

    uid: str | None = None
    source_label: str | None = None
    source_id: str | None = None
    article_id: str | None = None  # Alias for source_id
    title: str | None = None
    url: str | None = None
    published_at: str | None = None
    score: float | None = None
    rerank_score: float | None = None
    text_snippet: str | None = None

    # Relationship will be defined after both classes are declared


class IngestionRun(SQLModel, table=True):
    """Track ingestion runs for audit trail."""
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    source_type: str  # "rss", "yle", etc.
    source_ref: str  # Feed URL, API endpoint, etc.
    
    count_ingested: int = 0
    errors: List[str] = Field(default_factory=list, sa_column=Column(SQLJSON))
    
    # Optional metadata
    publisher: str | None = None
    user_id: str | None = None

# Define relationships after both classes are declared to avoid forward reference issues
# This pattern avoids SQLAlchemy's generic type annotation parsing issues
# See docs/sqlmodel_relationships.md for details on why this is necessary
ChatRun.hits: List["RetrievalHit"] = Relationship(back_populates="run")  # type: ignore
RetrievalHit.run: "ChatRun" = Relationship(back_populates="hits")  # type: ignore

def get_engine(db_url: str):
    return create_engine(db_url, echo=False)

def init_db(engine):
    SQLModel.metadata.create_all(engine)

def save_run(engine, run: ChatRun, hits: list[RetrievalHit]) -> ChatRun:
    with Session(engine) as s:
        s.add(run)
        s.commit()
        s.refresh(run)
        for rank, h in enumerate(hits, start=1):
            h.run_id = run.id  # type: ignore
            h.rank = rank
            s.add(h)
        s.commit()
        s.refresh(run)
        # Expunge to detach from session before returning
        s.expunge(run)
        return run


def save_ingestion_run(engine, run: IngestionRun) -> IngestionRun:
    """Save an ingestion run to audit DB."""
    with Session(engine) as s:
        s.add(run)
        s.commit()
        s.refresh(run)
        return run

def list_runs(engine, limit: int = 20) -> list[ChatRun]:
    with Session(engine) as s:
        # Query runs without eager loading hits (relationship might not be accessible)
        stmt = select(ChatRun).order_by(ChatRun.created_at.desc()).limit(limit)
        runs = list(s.exec(stmt).all())
        # Expunge to detach from session
        for run in runs:
            s.expunge(run)
        return runs

def read_run(engine, run_id: int) -> ChatRun | None:
    with Session(engine) as s:
        # Query run without eager loading hits
        stmt = select(ChatRun).where(ChatRun.id == run_id)
        run = s.exec(stmt).first()
        if run:
            # Load hits separately if needed
            hits_stmt = select(RetrievalHit).where(RetrievalHit.run_id == run_id).order_by(RetrievalHit.rank)
            hits = list(s.exec(hits_stmt).all())
            # Attach hits to run manually (for backward compatibility)
            if hasattr(run, 'hits'):
                run.hits = hits  # type: ignore
            # Expunge to detach from session
            s.expunge(run)
        return run
