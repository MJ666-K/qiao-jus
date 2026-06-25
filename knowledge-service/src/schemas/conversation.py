from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from schemas.search import Citation


class ConversationCreate(BaseModel):
    assistant_id: UUID
    title: str = Field(default="新对话", max_length=500)
    enable_thinking: bool | None = None


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
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
    assistant_id: UUID
    title: str
    enable_thinking: bool = True
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []


class ConversationSummary(BaseModel):
    id: UUID
    assistant_id: UUID
    title: str
    message_count: int = 0
    enable_thinking: bool = True
    created_at: datetime
    updated_at: datetime
