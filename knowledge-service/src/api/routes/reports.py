import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.deps import CurrentUserDep, SessionDep
from models.base import Document, Report
from pipeline.report_tasks import generate_report
from schemas.report import AnalyzeRequest, ReportOut, RiskItem
from schemas.search import Citation
from skills import load_skills

router = APIRouter(prefix="", tags=["reports"])

_DOC_TYPE_TO_REPORT_TYPE = {
    "contract": "contract_review",
    "dispute": "dispute_analysis",
    "report": "contract_review",
}


@router.post("/analyze", response_model=ReportOut, status_code=status.HTTP_202_ACCEPTED)
async def analyze(payload: AnalyzeRequest, user: CurrentUserDep, session: SessionDep):
    if not payload.source_doc_id and not payload.text:
        raise HTTPException(400, "must provide source_doc_id or text")

    source_doc = None
    doc_type_for_report = None
    if payload.source_doc_id:
        source_doc = await session.get(Document, payload.source_doc_id)
        if not source_doc or str(source_doc.dataset.tenant_id) != user.tenant_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "source document not found")
        doc_type_for_report = (source_doc.metadata_ or {}).get("doc_type", "contract")

    report_type = payload.report_type or _DOC_TYPE_TO_REPORT_TYPE.get(doc_type_for_report or "", "contract_review")

    report = Report(
        tenant_id=uuid.UUID(user.tenant_id),
        user_id=uuid.UUID(user.user_id),
        source_doc_id=source_doc.id if source_doc else None,
        type=report_type,
        status="pending",
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    generate_report.apply_async(
        kwargs={
            "report_id": str(report.id),
            "tenant_id": user.tenant_id,
            "user_id": user.user_id,
            "source_doc_id": str(payload.source_doc_id) if payload.source_doc_id else None,
            "report_type": report_type,
            "text": payload.text,
            "title": payload.title,
        },
        task_id=str(report.id),
    )
    return _to_out(report)


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(user: CurrentUserDep, session: SessionDep, limit: int = 50):
    res = await session.execute(
        select(Report)
        .where(Report.tenant_id == uuid.UUID(user.tenant_id))
        .order_by(Report.created_at.desc())
        .limit(limit)
    )
    return [_to_out(r) for r in res.scalars().all()]


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report(report_id: str, user: CurrentUserDep, session: SessionDep):
    r = await session.get(Report, uuid.UUID(report_id))
    if not r or str(r.tenant_id) != user.tenant_id:
        raise HTTPException(404, "report not found")
    return _to_out(r)


def _to_out(r: Report) -> ReportOut:
    content = r.content_json or {}
    risk_items = [
        RiskItem(**(ri if isinstance(ri, dict) else ri.model_dump()))
        for ri in content.get("risk_items", [])
    ]
    citations = [
        Citation(**(c if isinstance(c, dict) else c.model_dump()))
        for c in (r.citations_json or [])
    ]
    from schemas.report import EvidenceItem, LitigationParties
    parties = None
    if isinstance(content.get("parties"), dict):
        parties = LitigationParties(**content["parties"])
    evidence_items = [EvidenceItem(**ei) for ei in content.get("evidence_items", []) if isinstance(ei, dict)]
    return ReportOut(
        id=r.id,
        tenant_id=r.tenant_id,
        user_id=r.user_id,
        source_doc_id=r.source_doc_id,
        type=r.type,
        status=r.status,
        error=r.error,
        summary=r.summary,
        risk_items=risk_items,
        citations=citations,
        suggested_questions=r.suggested_questions or [],
        confidence=r.confidence,
        graph_path=r.graph_path or [],
        parties=parties,
        claims=content.get("claims", []) or [],
        facts=content.get("facts", []) or [],
        evidence_list=content.get("evidence_list", []) or [],
        evidence_items=evidence_items,
        procedure_steps=content.get("procedure_steps", []) or [],
        content_json=content,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )
