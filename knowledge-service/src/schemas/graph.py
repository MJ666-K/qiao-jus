from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    description: str | None = None
    properties: dict[str, Any] = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    description: str | None = None
    weight: float = 1.0


class GraphQueryResult(BaseModel):
    entities: list[GraphNode] = []
    relations: list[GraphEdge] = []
    related_chunks: list[dict[str, Any]] = []


class GraphQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    dataset_id: UUID | None = None
    depth: int = Field(default=2, ge=1, le=3)


class RelationMutation(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: str = "RELATED"
    description: str | None = None
