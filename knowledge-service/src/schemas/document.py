from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentStatus(BaseModel):
    id: UUID
    status: str
    error: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    user_id: UUID | None = None
    title: str
    source_uri: str | None
    mime_type: str | None
    content_hash: str | None
    status: str
    scope: str = "platform"
    error: str | None
    acl: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
