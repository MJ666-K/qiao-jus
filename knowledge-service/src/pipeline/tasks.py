from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

from core.config import settings
from core.llm import embed_texts
from ingest.chunker import build_parent_child
from ingest.parser import merge_blocks_to_text, parse_file
from models.base import Chunk, Document, IngestJob
from pipeline.celery_app import celery_app
from pipeline.graph_build import extract_entities_relations_sync
from storage.neo4j_client import sync_upsert_entities
from storage.postgres_sync import SyncSessionLocal
from storage.qdrant_client import make_point_id, upsert_points_sync

logger = logging.getLogger(__name__)

PENDING = "pending"
PARSING = "parsing"
CHUNKING = "chunking"
EMBEDDING = "embedding"
GRAPHING = "graphing"
DONE = "done"
FAILED = "failed"


def _set_status(session, doc_id: str, status: str, error: str | None = None) -> None:
    doc = session.get(Document, uuid.UUID(doc_id))
    if doc:
        doc.status = status
        if error:
            doc.error = error


def _record_job(session, doc_id: str, stage: str, status: str, result: dict | None = None) -> None:
    session.add(
        IngestJob(
            document_id=uuid.UUID(doc_id),
            stage=stage,
            status=status,
            result=result,
        )
    )


def _embed_batches(texts: list[str], batch: int = 16) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        out.extend(embed_texts(texts[i : i + batch]))
    return out


@celery_app.task(name="pipeline.tasks.parse_document", bind=True, max_retries=2)
def parse_document(self, doc_id: str, file_path: str) -> dict[str, Any]:
    with SyncSessionLocal() as session:
        try:
            _set_status(session, doc_id, PARSING)
            session.commit()

            blocks = parse_file(Path(file_path))
            text = merge_blocks_to_text(blocks)
            if not text:
                raise ValueError("empty content after parse")

            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            doc = session.get(Document, uuid.UUID(doc_id))
            doc.content_hash = content_hash
            doc.metadata_ = {**doc.metadata_, "blocks": len(blocks)}
            _record_job(session, doc_id, "parse", "done", {"chars": len(text)})
            session.commit()
            return {"doc_id": doc_id, "text": text, "chars": len(text), "hash": content_hash}
        except Exception as e:
            _set_status(session, doc_id, FAILED, str(e))
            _record_job(session, doc_id, "parse", "failed", {"error": str(e)})
            session.commit()
            raise self.retry(exc=e, countdown=2 ** self.request.retries)


@celery_app.task(name="pipeline.tasks.chunk_and_embed", bind=True, max_retries=2)
def chunk_and_embed(
    self,
    parse_result: dict[str, Any],
    doc_id: str,
    dataset_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Chunk parsed text into parent/child units, embed children, upsert to Qdrant.

    Children carry embeddings + parent_id in Qdrant payload; parents are stored
    only in Postgres so retrieval can expand a hit into a fuller context window."""
    text = parse_result["text"]
    parents, parent_child_texts = build_parent_child(text)
    if not parents:
        raise ValueError("no chunks produced from text")

    with SyncSessionLocal() as session:
        try:
            _set_status(session, doc_id, CHUNKING)
            session.commit()

            parent_rows: list[Chunk] = []
            for i, ptext in enumerate(parents):
                parent = Chunk(
                    document_id=uuid.UUID(doc_id),
                    parent_id=None,
                    chunk_index=i,
                    text=ptext,
                    token_count=len(ptext),
                    char_count=len(ptext),
                )
                session.add(parent)
                parent_rows.append(parent)
            session.flush()

            child_payload: list[Chunk] = []
            global_idx = 0
            for parent_idx, child_texts in enumerate(parent_child_texts):
                parent = parent_rows[parent_idx]
                for child_text in child_texts:
                    c = Chunk(
                        document_id=uuid.UUID(doc_id),
                        parent_id=parent.id,
                        chunk_index=global_idx,
                        text=child_text,
                        token_count=len(child_text),
                        char_count=len(child_text),
                    )
                    session.add(c)
                    child_payload.append(c)
                    global_idx += 1
            session.flush()

            child_text_list = [c.text for c in child_payload]
            embeddings = _embed_batches(child_text_list)

            points = []
            for c, vec in zip(child_payload, embeddings, strict=True):
                # Qdrant point id == Chunk.id so that RRF over dense + BM25 can
                # treat them as the same identifier without an extra lookup.
                pid = str(c.id)
                c.qdrant_id = uuid.UUID(pid)
                c.embedding_model = settings.embedding_model_id
                points.append({
                    "id": pid,
                    "vector": vec,
                    "payload": {
                        "document_id": doc_id,
                        "dataset_id": dataset_id,
                        "tenant_id": tenant_id,
                        "parent_id": str(c.parent_id),
                        "chunk_index": c.chunk_index,
                        "text": c.text,
                    },
                })
            if points:
                upsert_points_sync(points)

            _set_status(session, doc_id, EMBEDDING)
            _record_job(session, doc_id, "embed", "done", {"chunks": len(points)})
            session.commit()

            return {
                "doc_id": doc_id,
                "dataset_id": dataset_id,
                "tenant_id": tenant_id,
                "chunks": len(child_payload),
            }
        except Exception as e:
            _set_status(session, doc_id, FAILED, str(e))
            _record_job(session, doc_id, "embed", "failed", {"error": str(e)})
            session.commit()
            raise self.retry(exc=e, countdown=2 ** self.request.retries)


@celery_app.task(name="pipeline.tasks.build_graph", bind=True, max_retries=1)
def build_graph(self, embed_result: dict[str, Any], doc_id: str) -> dict[str, Any]:
    with SyncSessionLocal() as session:
        try:
            _set_status(session, doc_id, GRAPHING)
            session.commit()

            res = session.execute(
                select(Chunk).where(
                    Chunk.document_id == uuid.UUID(doc_id), Chunk.parent_id.is_(None)
                )
            )
            parent_chunks = res.scalars().all()

            total_entities = 0
            for chunk in parent_chunks:
                ents, rels = extract_entities_relations_sync(chunk.text)
                if not ents:
                    continue
                sync_upsert_entities(
                    tenant_id=embed_result["tenant_id"],
                    dataset_id=embed_result["dataset_id"],
                    document_id=doc_id,
                    chunk_id=str(chunk.id),
                    entities=ents,
                    relations=rels,
                )
                total_entities += len(ents)

            # Rebuild communities after new entities landed. Best-effort: failure
            # here does not fail the document (graph global is a v0.5 add-on).
            community_stats = {"communities": 0, "entities_covered": 0}
            try:
                from pipeline.community import detect_and_write_communities
                community_stats = detect_and_write_communities(embed_result["tenant_id"])
            except Exception as e:
                logger.warning("community detection skipped: %s", e)

            _set_status(session, doc_id, DONE)
            _record_job(session, doc_id, "graph", "done", {
                "entities": total_entities, **community_stats,
            })
            session.commit()
            return {"doc_id": doc_id, "entities": total_entities, **community_stats}
        except Exception as e:
            _set_status(session, doc_id, FAILED, str(e))
            _record_job(session, doc_id, "graph", "failed", {"error": str(e)})
            session.commit()
            raise self.retry(exc=e, countdown=2 ** self.request.retries)


@celery_app.task(name="pipeline.tasks.reindex_document")
def reindex_document(doc_id: str, file_path: str, dataset_id: str, tenant_id: str) -> str:
    """Incremental re-index: wipe all chunks/qdrant points/graph nodes for the
    document, then run parse → chunk → embed → graph end-to-end. Used by the
    PUT /documents/{id}/reindex endpoint when the source file changes."""
    from storage.neo4j_client import sync_delete_by_document
    from storage.qdrant_client import delete_by_document_sync

    sync_delete_by_document(doc_id)
    delete_by_document_sync(doc_id)
    with SyncSessionLocal() as session:
        session.execute(
            select(Chunk).where(Chunk.document_id == uuid.UUID(doc_id))
        ).scalar()
        from sqlalchemy import delete as sql_delete
        session.execute(sql_delete(Chunk).where(Chunk.document_id == uuid.UUID(doc_id)))
        doc = session.get(Document, uuid.UUID(doc_id))
        if doc:
            doc.status = PENDING
            doc.error = None
        session.commit()

    chain = parse_document.s(doc_id, file_path) | chunk_and_embed.s(
        doc_id, dataset_id, tenant_id
    ) | build_graph.s(doc_id)
    chain.apply_async()
    return doc_id
