from __future__ import annotations

import asyncio
import logging
import uuid

from models.base import Report
from pipeline.celery_app import celery_app
from storage.postgres_sync import SyncSessionLocal

logger = logging.getLogger(__name__)

PENDING = "pending"
GENERATING = "generating"
DONE = "done"
FAILED = "failed"


def _set_status(report_id: str, status: str, error: str | None = None) -> None:
    with SyncSessionLocal() as session:
        r = session.get(Report, uuid.UUID(report_id))
        if r:
            r.status = status
            if error:
                r.error = error
            session.commit()


@celery_app.task(
    name="pipeline.report_tasks.generate_report",
    bind=True,
    max_retries=1,
)
def generate_report(
    self,
    report_id: str,
    tenant_id: str,
    user_id: str,
    source_doc_id: str | None = None,
    report_type: str = "contract_review",
    text: str | None = None,
    title: str | None = None,
) -> str:
    try:
        asyncio.run(_async_generate(
            report_id, tenant_id, user_id, source_doc_id, report_type, text, title
        ))
        return report_id
    except Exception as e:
        logger.exception("generate_report failed report_id=%s", report_id)
        _set_status(report_id, FAILED, str(e))
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


async def _async_generate(
    report_id: str,
    tenant_id: str,
    user_id: str,
    source_doc_id: str | None,
    report_type: str,
    text: str | None,
    title: str | None,
) -> None:
    _set_status(report_id, GENERATING)

    from skills import load_skills
    from skills.registry import SkillRegistry

    load_skills()
    skill = SkillRegistry.get("report_generation")
    if not skill:
        raise RuntimeError("report_generation skill not registered")

    skill_params: dict = {
        "tenant_id": tenant_id,
        "report_type": report_type,
    }
    if source_doc_id:
        skill_params["source_doc_id"] = source_doc_id
    elif text:
        skill_params["text"] = text

    result = await skill.execute(skill_params)

    from storage.postgres import SessionLocal

    async with SessionLocal() as session:
        r = await session.get(Report, uuid.UUID(report_id))
        if not r:
            raise RuntimeError(f"report {report_id} vanished during generation")
        r.summary = result["summary"]
        r.content_json = {
            "risk_items": result["risk_items"],
            "graph_path": result["graph_path"],
        }
        r.citations_json = result["citations"]
        r.suggested_questions = result["suggested_questions"]
        r.confidence = result["confidence"]
        r.graph_path = result["graph_path"]
        r.status = DONE
        await session.commit()

    _persist_report_chunks(report_id, tenant_id, user_id, result, title or f"{report_type} 报告")


def _persist_report_chunks(
    report_id: str,
    tenant_id: str,
    user_id: str,
    result: dict,
    title: str,
) -> None:
    """Convert the generated report into searchable chunks so subsequent
    report-bound Q&A can RAG over the user's report content."""
    from core.llm import embed_texts
    from ingest.chunker import build_parent_child
    from ingest.doc_types import REPORT
    from models.base import Chunk, Dataset, Document
    from storage.qdrant_client import upsert_points_sync

    sections = [result.get("summary") or ""]
    for ri in result.get("risk_items", []):
        if isinstance(ri, dict):
            sections.append(
                f"[{ri.get('level', '中')}] {ri.get('desc', '')}"
                + (f"（{ri.get('law_ref')}）" if ri.get("law_ref") else "")
                + (f"\n建议：{ri.get('suggestion')}" if ri.get("suggestion") else "")
            )
    text_body = "\n\n".join(s for s in sections if s)
    if not text_body.strip():
        return

    with SyncSessionLocal() as session:
        ds = session.execute(
            __import__("sqlalchemy").select(Dataset).where(
                Dataset.tenant_id == uuid.UUID(tenant_id),
                Dataset.name == "用户报告库",
            )
        ).scalars().first()
        if not ds:
            ds = Dataset(
                tenant_id=uuid.UUID(tenant_id),
                name="用户报告库",
                description="系统生成的分析报告",
                metadata_={"scope": "user", "doc_type": REPORT},
            )
            session.add(ds)
            session.flush()

        doc = Document(
            dataset_id=ds.id,
            user_id=uuid.UUID(user_id),
            title=title,
            source_uri=f"report://{report_id}",
            status="done",
            scope="user",
            metadata_={
                "doc_type": REPORT,
                "scope": "user",
                "report_id": report_id,
                "report_type": result.get("report_type"),
                "risk_level": _dominant_risk_level(result.get("risk_items", [])),
            },
        )
        session.add(doc)
        session.flush()

        units = build_parent_child(text_body, REPORT, dict(doc.metadata_ or {}))
        parent_rows = [u for u in units if u.is_parent]
        child_units = [u for u in units if not u.is_parent]

        rows = []
        for i, u in enumerate(parent_rows):
            c = Chunk(
                document_id=doc.id,
                parent_id=None,
                chunk_index=i,
                text=u.text,
                token_count=len(u.text),
                char_count=len(u.text),
                scope="user",
                metadata_=u.metadata,
            )
            session.add(c)
            rows.append(c)
        session.flush()
        parent_map = {p.chunk_index: p for p in rows}
        children = []
        global_idx = 0
        for u in child_units:
            parent_row = parent_map.get(u.parent_index)
            c = Chunk(
                document_id=doc.id,
                parent_id=parent_row.id if parent_row else None,
                chunk_index=global_idx,
                text=u.text,
                token_count=len(u.text),
                char_count=len(u.text),
                scope="user",
                metadata_=u.metadata,
            )
            session.add(c)
            children.append(c)
            global_idx += 1
        if not children:
            children = rows
        session.flush()

        if children:
            embeddings = embed_texts([c.text for c in children])
            points = []
            for c, vec in zip(children, embeddings, strict=True):
                pid = str(c.id)
                c.qdrant_id = uuid.UUID(pid)
                meta = c.metadata_ or {}
                points.append({
                    "id": pid,
                    "vector": vec,
                    "payload": {
                        "document_id": str(doc.id),
                        "dataset_id": str(ds.id),
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "scope": "user",
                        "parent_id": str(c.parent_id) if c.parent_id else str(c.id),
                        "chunk_index": c.chunk_index,
                        "text": c.text,
                        "doc_type": REPORT,
                        "report_type": meta.get("report_type"),
                        "risk_level": meta.get("risk_level"),
                    },
                })
            if points:
                upsert_points_sync(points)
        session.commit()


def _dominant_risk_level(risk_items: list) -> str:
    if not risk_items:
        return "中"
    levels = [ri.get("level", "中") for ri in risk_items if isinstance(ri, dict)]
    if "高" in levels:
        return "高"
    if "中" in levels:
        return "中"
    return "低"
