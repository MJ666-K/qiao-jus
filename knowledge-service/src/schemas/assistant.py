from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AssistantCreate(BaseModel):
    name: str = Field(default="新助手", max_length=200)
    description: str | None = None
    dataset_ids: list[UUID] = Field(default_factory=list)
    report_ids: list[UUID] = Field(default_factory=list)
    enable_thinking: bool = Field(default=True)


class AssistantUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    dataset_ids: list[UUID] | None = None
    report_ids: list[UUID] | None = None
    enable_thinking: bool | None = None


class AssistantOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    dataset_ids: list[UUID] = []
    report_ids: list[UUID] = []
    enable_thinking: bool = True
    conversation_count: int = 0
    created_at: datetime
    updated_at: datetime


class AssistantSummary(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    dataset_ids: list[UUID] = []
    report_ids: list[UUID] = []
    conversation_count: int = 0
    created_at: datetime
    updated_at: datetime
