from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from schemas.search import Citation


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", max_length=500)
    report_id: UUID | None = None
    report_ids: list[UUID] = Field(default_factory=list)
    dataset_ids: list[UUID] = Field(default_factory=list)
    track: str | None = Field(default=None, max_length=30)
    enable_thinking: bool = Field(default=True)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    report_id: UUID | None = None
    report_ids: list[UUID] | None = None
    dataset_ids: list[UUID] | None = None
    track: str | None = Field(default=None, max_length=30)
    enable_thinking: bool | None = None


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    confidence: int | None = None
    suggested_questions: list[str] = []
    citations: list[Citation] = []
    created_at: datetime


class ConversationOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    report_id: UUID | None = None
    report_ids: list[UUID] = []
    dataset_ids: list[UUID] = []
    title: str
    track: str | None = None
    enable_thinking: bool = True
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    report_id: UUID | None = None
    report_ids: list[UUID] = []
    dataset_ids: list[UUID] = []
    track: str | None = None
    message_count: int = 0
    enable_thinking: bool = True
    created_at: datetime
    updated_at: datetime
