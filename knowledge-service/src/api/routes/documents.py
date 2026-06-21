import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from api.deps import CurrentUserDep, SessionDep
from core.config import settings
from models.base import Dataset, Document
from ingest.doc_types import DOC_TYPE_LABELS, GENERAL
from pipeline.tasks import build_graph, chunk_and_embed, parse_document, reindex_document
from schemas.document import DocumentOut

VALID_DOC_TYPES = set(DOC_TYPE_LABELS.keys())

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    user: CurrentUserDep,
    session: SessionDep,
    dataset_id: str | None = None,
    status_filter: str | None = None,
    doc_type: str | None = None,
    limit: int = 100,
):
    """List documents for the current tenant, optionally filtered by dataset/status."""
    stmt = (
        select(Document)
        .options(joinedload(Document.dataset))
        .join(Dataset, Document.dataset_id == Dataset.id)
        .where(Dataset.tenant_id == _uuid(user.tenant_id))
    )
    if dataset_id:
        stmt = stmt.where(Document.dataset_id == _uuid(dataset_id))
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)
    if doc_type:
        stmt = stmt.where(Document.metadata_["doc_type"].astext == doc_type)
    stmt = stmt.order_by(Document.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    return [DocumentOut.model_validate(_as_out(d)) for d in res.scalars().unique().all()]


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    dataset_id: str,
    user: CurrentUserDep,
    session: SessionDep,
    doc_type: str = Query(default=GENERAL, description="文档类型: law/case/compliance/..."),
):
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid doc_type, choose from {sorted(VALID_DOC_TYPES)}")
    ds = await session.get(Dataset, uuid.UUID(dataset_id))
    if not ds or str(ds.tenant_id) != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dataset not found")

    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")
    content_hash = hashlib.sha256(raw).hexdigest()

    existing = await session.execute(
        select(Document).where(
            Document.dataset_id == ds.id, Document.content_hash == content_hash
        )
    )
    dup = existing.scalars().first()
    if dup:
        return DocumentOut.model_validate(_as_out(dup))

    file_path = settings.uploads_dir / f"{uuid.uuid4().hex}_{file.filename}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(raw)

    ds_meta = dict(ds.metadata_ or {})
    doc_meta = {
        "doc_type": doc_type,
        "original_filename": file.filename,
        "scope": ds_meta.get("scope", "platform"),
    }
    if ds_meta.get("domain"):
        doc_meta["domain"] = ds_meta["domain"]
    if ds_meta.get("law_name"):
        doc_meta["law_name"] = ds_meta["law_name"]

    doc = Document(
        dataset_id=ds.id,
        title=file.filename or "untitled",
        source_uri=str(file_path),
        content_hash=content_hash,
        mime_type=file.content_type,
        status="pending",
        metadata_=doc_meta,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    chain = parse_document.s(str(doc.id), str(file_path)) | chunk_and_embed.s(
        str(doc.id), str(ds.id), user.tenant_id
    ) | build_graph.s(str(doc.id))
    chain.apply_async()

    return DocumentOut.model_validate(_as_out(doc))


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, user: CurrentUserDep, session: SessionDep):
    res = await session.execute(
        select(Document).options(joinedload(Document.dataset)).where(Document.id == uuid.UUID(document_id))
    )
    doc = res.scalars().first()
    if not doc or str(doc.dataset.tenant_id) != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return DocumentOut.model_validate(_as_out(doc))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, user: CurrentUserDep, session: SessionDep):
    from storage.neo4j_client import delete_by_document as graph_delete
    from storage.qdrant_client import delete_by_document as vec_delete

    res = await session.execute(
        select(Document).options(joinedload(Document.dataset)).where(Document.id == uuid.UUID(document_id))
    )
    doc = res.scalars().first()
    if not doc or str(doc.dataset.tenant_id) != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    await vec_delete(str(doc.id))
    await graph_delete(str(doc.id))
    await session.delete(doc)
    await session.commit()


@router.post("/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_document_endpoint(document_id: str, user: CurrentUserDep, session: SessionDep):
    """Trigger incremental re-indexing: wipes chunks/vectors/graph for this doc
    and re-runs the full pipeline. Use when the underlying file changes."""
    res = await session.execute(
        select(Document).options(joinedload(Document.dataset)).where(Document.id == uuid.UUID(document_id))
    )
    doc = res.scalars().first()
    if not doc or str(doc.dataset.tenant_id) != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    if not doc.source_uri or not Path(doc.source_uri).exists():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "source file not found")
    reindex_document.delay(
        str(doc.id), doc.source_uri, str(doc.dataset_id), user.tenant_id
    )
    return {"id": str(doc.id), "status": "queued", "message": "reindexing started"}


def _uuid(s: str):
    return uuid.UUID(s)


def _as_out(doc: Document) -> dict:
    return {
        "id": doc.id,
        "dataset_id": doc.dataset_id,
        "title": doc.title,
        "source_uri": doc.source_uri,
        "mime_type": doc.mime_type,
        "content_hash": doc.content_hash,
        "status": doc.status,
        "error": doc.error,
        "acl": doc.acl,
        "metadata": doc.metadata_,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }
