from fastapi import APIRouter
from sqlalchemy import func, select

from api.deps import CurrentUserDep, SessionDep
from models.base import Chunk, Dataset, Document, IngestJob

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def tenant_stats(user: CurrentUserDep, session: SessionDep):
    """Aggregate counts for the current tenant. Powers the dashboard."""
    tenant_uuid = _uuid(user.tenant_id)

    datasets_count = await session.scalar(
        select(func.count(Dataset.id)).where(Dataset.tenant_id == tenant_uuid)
    )
    docs_count = await session.scalar(
        select(func.count(Document.id))
        .join(Dataset, Document.dataset_id == Dataset.id)
        .where(Dataset.tenant_id == tenant_uuid)
    )
    done_count = await session.scalar(
        select(func.count(Document.id))
        .join(Dataset, Document.dataset_id == Dataset.id)
        .where(Dataset.tenant_id == tenant_uuid, Document.status == "done")
    )
    chunks_count = await session.scalar(
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Dataset, Document.dataset_id == Dataset.id)
        .where(Dataset.tenant_id == tenant_uuid)
    )
    jobs_recent = await session.execute(
        select(IngestJob.stage, IngestJob.status, func.count(IngestJob.id).label("n"))
        .join(Document, IngestJob.document_id == Document.id)
        .join(Dataset, Document.dataset_id == Dataset.id)
        .where(Dataset.tenant_id == tenant_uuid)
        .group_by(IngestJob.stage, IngestJob.status)
    )
    job_breakdown = [
        {"stage": r.stage, "status": r.status, "count": r.n} for r in jobs_recent.all()
    ]

    from storage.qdrant_client import get_client
    try:
        client = get_client()
        qinfo = await client.get_collection("knowledge")
        qdrant_points = qinfo.points_count or 0
    except Exception:
        qdrant_points = 0

    return {
        "datasets": datasets_count or 0,
        "documents": docs_count or 0,
        "documents_done": done_count or 0,
        "chunks": chunks_count or 0,
        "qdrant_points": qdrant_points,
        "job_breakdown": job_breakdown,
    }


def _uuid(s: str):
    import uuid

    return uuid.UUID(s)
