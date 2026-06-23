from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from schemas.search import Citation


ReportType = Literal["contract_review", "dispute_analysis", "labor_risk", "litigation_draft", "evidence_checklist"]


class AnalyzeRequest(BaseModel):
    source_doc_id: UUID | None = Field(default=None, description="已上传的源文档 ID；与 text 二选一")
    text: str | None = Field(default=None, description="直接输入文本（M3/M4/M5 无需上传文档时使用）")
    title: str | None = Field(default=None, description="直接输入模式下的标题")
    report_type: ReportType | None = Field(default=None, description="报告类型；不传则按源文档 doc_type 推断")
    extra_context: str | None = Field(default=None, description="用户附加说明（可空）")


class RiskItem(BaseModel):
    level: Literal["高", "中", "低"] = "中"
    desc: str
    law_ref: str | None = None
    chunk_id: str | None = None
    suggestion: str | None = None


class EvidenceItem(BaseModel):
    name: str
    level: Literal["高", "中", "低"] = "中"
    purpose: str | None = None
    collect_tip: str | None = None


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
