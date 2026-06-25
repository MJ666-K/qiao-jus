from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from schemas.search import Citation


ReportType = Literal["contract_review", "dispute_analysis", "labor_risk", "litigation_draft", "evidence_checklist"]

_LEVEL_ALIASES = {
    "high": "高",
    "h": "高",
    "medium": "中",
    "med": "中",
    "m": "中",
    "low": "低",
    "l": "低",
    "高": "高",
    "中": "中",
    "低": "低",
}


def normalize_level(value: object) -> str:
    if value is None:
        return "中"
    raw = str(value).strip()
    mapped = _LEVEL_ALIASES.get(raw.lower()) or _LEVEL_ALIASES.get(raw)
    return mapped or "中"


class AnalyzeRequest(BaseModel):
    source_doc_id: UUID | None = Field(default=None, description="已上传的源文档 ID（单选，兼容旧客户端）")
    source_doc_ids: list[UUID] | None = Field(default=None, description="已上传的源文档 ID 列表（多选）")
    text: str | None = Field(default=None, description="直接输入文本（M3/M4/M5 无需上传文档时使用）")
    title: str | None = Field(default=None, description="直接输入模式下的标题")
    report_type: ReportType | None = Field(default=None, description="报告类型；不传则按源文档 doc_type 推断")
    extra_context: str | None = Field(default=None, description="用户附加说明（可空）")

    def resolved_doc_ids(self) -> list[UUID]:
        if self.source_doc_ids:
            return list(self.source_doc_ids)
        if self.source_doc_id:
            return [self.source_doc_id]
        return []


class RiskItem(BaseModel):
    level: Literal["高", "中", "低"] = "中"
    desc: str
    law_ref: str | None = None
    chunk_id: str | None = None
    suggestion: str | None = None

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, v: object) -> str:
        return normalize_level(v)


class EvidenceItem(BaseModel):
    name: str
    level: Literal["高", "中", "低"] = "中"
    purpose: str | None = None
    collect_tip: str | None = None

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, v: object) -> str:
        return normalize_level(v)


class LitigationParties(BaseModel):
    plaintiff: str | None = None
    defendant: str | None = None


class ReportOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    source_doc_id: UUID | None = None
    type: ReportType
    status: str = "pending"
    error: str | None = None
    summary: str | None = None
    risk_items: list[RiskItem] = []
    citations: list[Citation] = []
    suggested_questions: list[str] = []
    confidence: int = 0
    graph_path: list[str] = []
    parties: LitigationParties | None = None
    claims: list[str] = []
    facts: list[str] = []
    evidence_list: list[dict[str, Any]] = []
    evidence_items: list[EvidenceItem] = []
    procedure_steps: list[str] = []
    content_json: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
