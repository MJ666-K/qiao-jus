import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

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


async def _load_source_docs(session: SessionDep, doc_ids: list[uuid.UUID], tenant_id: str) -> list[Document]:
    if not doc_ids:
        return []
    res = await session.execute(
        select(Document)
        .options(joinedload(Document.dataset))
        .where(Document.id.in_(doc_ids))
    )
    found = {d.id: d for d in res.scalars().unique().all()}
    source_docs: list[Document] = []
    for doc_id in doc_ids:
        doc = found.get(doc_id)
        if not doc or str(doc.dataset.tenant_id) != tenant_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"source document not found: {doc_id}")
        source_docs.append(doc)
    return source_docs


@router.post("/analyze", response_model=ReportOut, status_code=status.HTTP_202_ACCEPTED)
async def analyze(payload: AnalyzeRequest, user: CurrentUserDep, session: SessionDep):
    doc_ids = payload.resolved_doc_ids()
    if not doc_ids and not payload.text:
        raise HTTPException(400, "must provide source_doc_id(s) or text")

    source_docs = await _load_source_docs(session, doc_ids, user.tenant_id)

    doc_type_for_report = None
    if source_docs:
        doc_type_for_report = (source_docs[0].metadata_ or {}).get("doc_type", "contract")

    report_type = payload.report_type or _DOC_TYPE_TO_REPORT_TYPE.get(doc_type_for_report or "", "contract_review")

    report = Report(
        tenant_id=uuid.UUID(user.tenant_id),
        user_id=uuid.UUID(user.user_id),
        source_doc_id=source_docs[0].id if source_docs else None,
        type=report_type,
        status="pending",
        content_json={"source_doc_ids": [str(d.id) for d in source_docs]} if source_docs else {},
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    generate_report.apply_async(
        kwargs={
            "report_id": str(report.id),
            "tenant_id": user.tenant_id,
            "user_id": user.user_id,
            "source_doc_id": str(source_docs[0].id) if source_docs else None,
            "source_doc_ids": [str(d.id) for d in source_docs] if source_docs else None,
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
