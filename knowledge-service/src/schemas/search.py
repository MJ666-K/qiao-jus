from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    query: str = Field(min_length=1)
    dataset_id: UUID | None = None
    doc_type: str | None = None
    filters: dict[str, Any] = {}
    top_k: int = Field(default=10, ge=1, le=50)
    use_graph: bool = True


SourceType = Literal["law", "case", "report", "user_doc", "compliance", "graph"]


class Citation(BaseModel):
    chunk_id: str | None = None
    document_id: str | None = None
    source_type: SourceType
    source_title: str
    excerpt: str | None = None
    page: int | None = None
    score: float | None = None


class SearchHit(BaseModel):
    chunk_id: str
    text: str
    score: float
    source: str | None = None
    document_id: str | None = None
    page: int | None = None
    metadata: dict[str, Any] = {}
    doc_type: str | None = None
    article_no: str | None = None
    law_name: str | None = None
    source_type: SourceType | None = None
    source_title: str | None = None
    excerpt: str | None = None


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit]
    graph_context: list[dict[str, Any]] = []


class AnswerResult(BaseModel):
    query: str
    answer: str
    sources: list[SearchHit] = []
    citations: list[Citation] = []
    graph_entities: list[str] = []
    suggested_questions: list[str] = []
    confidence: int | None = None
