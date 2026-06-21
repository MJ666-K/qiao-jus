from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    query: str = Field(min_length=1)
    dataset_id: UUID | None = None
    filters: dict[str, Any] = {}
    top_k: int = Field(default=10, ge=1, le=50)
    use_graph: bool = True


class SearchHit(BaseModel):
    chunk_id: str
    text: str
    score: float
    source: str | None = None
    document_id: str | None = None
    page: int | None = None
    metadata: dict[str, Any] = {}


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit]
    graph_context: list[dict[str, Any]] = []


class AnswerResult(BaseModel):
    query: str
    answer: str
    sources: list[SearchHit] = []
    graph_entities: list[str] = []
