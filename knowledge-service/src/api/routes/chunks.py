import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import CurrentUserDep, SessionDep
from models.base import Chunk, Dataset, Document
from storage.qdrant_client import upsert_points_sync

router = APIRouter(prefix="/documents", tags=["chunks"])


class ChunkOut(BaseModel):
    id: str
    document_id: str
    parent_id: str | None = None
    chunk_index: int
    text: str
    token_count: int | None = None
    char_count: int | None = None
    scope: str = "platform"
    metadata: dict = {}


class ChunkUpdate(BaseModel):
    text: str
    re_embed: bool = True


async def _check_doc_access(document_id: str, tenant_id: str, session) -> None:
    res = await session.execute(
        select(Dataset.tenant_id)
        .join(Document, Document.dataset_id == Dataset.id)
        .where(Document.id == uuid.UUID(document_id))
    )
    row = res.first()
    if not row or str(row[0]) != tenant_id:
        raise HTTPException(404, "document not found")


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
async def list_chunks(document_id: str, user: CurrentUserDep, session: SessionDep):
    await _check_doc_access(document_id, user.tenant_id, session)
    res = await session.execute(
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.parent_id,
            Chunk.chunk_index,
            Chunk.text,
            Chunk.token_count,
            Chunk.char_count,
            Chunk.scope,
            Chunk.metadata_,
        )
        .where(Chunk.document_id == uuid.UUID(document_id))
        .order_by(Chunk.chunk_index)
    )
    return [
        ChunkOut(
            id=str(row.id),
            document_id=str(row.document_id),
            parent_id=str(row.parent_id) if row.parent_id else None,
            chunk_index=row.chunk_index,
            text=row.text,
            token_count=row.token_count,
            char_count=row.char_count,
            scope=row.scope,
            metadata=row.metadata_ or {},
        )
        for row in res.all()
    ]


@router.put("/{document_id}/chunks/{chunk_id}", response_model=ChunkOut)
async def update_chunk(
    document_id: str,
    chunk_id: str,
    payload: ChunkUpdate,
    user: CurrentUserDep,
    session: SessionDep,
):
    await _check_doc_access(document_id, user.tenant_id, session)
    c = await session.get(Chunk, uuid.UUID(chunk_id))
    if not c or str(c.document_id) != document_id:
        raise HTTPException(404, "chunk not found")

    c.text = payload.text
    c.char_count = len(payload.text)
    c.token_count = len(payload.text)

    if payload.re_embed:
        from core.llm import embed_texts
        vecs = embed_texts([payload.text])
        if vecs:
            doc_res = await session.execute(
                select(Document.dataset_id).where(Document.id == uuid.UUID(document_id))
            )
            ds_row = doc_res.first()
            upsert_points_sync([{
                "id": str(c.id),
                "vector": vecs[0],
                "payload": {
                    "document_id": str(c.document_id),
                    "dataset_id": str(ds_row[0]) if ds_row else "",
                    "tenant_id": user.tenant_id,
                    "scope": c.scope,
                    "parent_id": str(c.parent_id) if c.parent_id else str(c.id),
                    "chunk_index": c.chunk_index,
                    "text": payload.text,
                    **(c.metadata_ or {}),
                },
            }])

    await session.commit()
    await session.refresh(c)
    return ChunkOut(
        id=str(c.id),
        document_id=str(c.document_id),
        parent_id=str(c.parent_id) if c.parent_id else None,
        chunk_index=c.chunk_index,
        text=c.text,
        token_count=c.token_count,
        char_count=c.char_count,
        scope=c.scope,
        metadata=c.metadata_ or {},
    )


@router.delete("/{document_id}/chunks/{chunk_id}", status_code=204)
async def delete_chunk(
    document_id: str,
    chunk_id: str,
    user: CurrentUserDep,
    session: SessionDep,
):
    await _check_doc_access(document_id, user.tenant_id, session)
    c = await session.get(Chunk, uuid.UUID(chunk_id))
    if not c or str(c.document_id) != document_id:
        raise HTTPException(404, "chunk not found")
    await session.delete(c)
    await session.commit()
