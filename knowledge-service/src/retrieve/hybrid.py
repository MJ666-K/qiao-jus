from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.llm import embed_texts
from models.base import Chunk, Dataset, Document
from retrieve.bm25 import BM25Index
from retrieve.reranker import get_reranker
from storage.postgres import SessionLocal
from storage.qdrant_client import search_dense

logger = logging.getLogger(__name__)


async def retrieve_children(
    query: str,
    tenant_id: str,
    dataset_id: str | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Hybrid retrieval over child chunks. Combines Qdrant dense search with a
    BM25 sparse index built from current tenant's chunks via Reciprocal Rank
    Fusion. Returns fused, reranked hits with parent context attached."""
    top_k = top_k or settings.search_top_k
    dense_filters: dict[str, Any] = {"tenant_id": tenant_id}
    if dataset_id:
        dense_filters["dataset_id"] = dataset_id

    query_vec_list = await asyncio.to_thread(embed_texts, [query])
    query_vec = query_vec_list[0]

    dense_task = search_dense(query_vec, dense_filters, top_k * 3)
    bm25_task = _bm25_search(query, tenant_id, dataset_id, top_k * 3)
    dense_hits, bm25_hits = await asyncio.gather(dense_task, bm25_task)

    fused = rrf_fusion(
        dense=[(h.id, h.score or 0.0) for h in dense_hits],
        sparse=[(h["id"], h["score"]) for h in bm25_hits],
    )

    if not fused:
        return []

    ids = [uuid.UUID(pid) for pid, _ in fused[: settings.rerank_top_k]]
    rows = await _fetch_chunks_with_parents(ids)

    by_id = {str(r["child_id"]): r for r in rows}
    candidates: list[dict[str, Any]] = []
    for pid, score in fused:
        if pid not in by_id:
            continue
        r = by_id[pid]
        parent_key = str(r["parent_id"]) if r["parent_id"] else pid
        candidates.append({
            "chunk_id": parent_key,
            "text": r["parent_text"] or r["child_text"],
            "score": float(score),
            "source": r["title"],
            "document_id": str(r["document_id"]),
            "page": r.get("page"),
            "_raw_pid": pid,
        })

    reranked = await get_reranker().rank(query, candidates, top_k=top_k)

    out: list[dict[str, Any]] = []
    seen_parents: set[str] = set()
    for r in reranked:
        parent_key = r["chunk_id"]
        if parent_key in seen_parents:
            continue
        seen_parents.add(parent_key)
        out.append({
            "chunk_id": parent_key,
            "text": r["text"],
            "score": r.get("_rerank_score", r["score"]),
            "source": r["source"],
            "document_id": r["document_id"],
            "page": r.get("page"),
        })
        if len(out) >= top_k:
            break
    return out


async def _fetch_chunks_with_parents(child_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        res = await session.execute(
            select(Chunk, Document.title)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.id.in_(child_ids))
        )
        rows: list[dict[str, Any]] = []
        parent_ids: list[uuid.UUID] = []
        for c, title in res.all():
            rows.append({
                "child_id": c.id,
                "child_text": c.text,
                "parent_id": c.parent_id,
                "document_id": c.document_id,
                "title": title,
            })
            if c.parent_id and c.parent_id not in parent_ids:
                parent_ids.append(c.parent_id)
        if parent_ids:
            pres = await session.execute(select(Chunk).where(Chunk.id.in_(parent_ids)))
            pmap = {p.id: p.text for p in pres.scalars()}
        else:
            pmap = {}
        for r in rows:
            r["parent_text"] = pmap.get(r["parent_id"]) if r["parent_id"] else None
        return rows


async def _bm25_search(
    query: str, tenant_id: str, dataset_id: str | None, top_k: int
) -> list[dict[str, Any]]:
    corpus = await _load_corpus(tenant_id, dataset_id)
    if not corpus:
        return []
    bm25 = BM25Index(corpus=[c["text"] for c in corpus])
    scores = bm25.get_scores(query)
    ranked = sorted(zip(corpus, scores, strict=True), key=lambda x: x[1], reverse=True)[:top_k]
    return [{"id": str(c["id"]), "score": float(s)} for c, s in ranked if s > 0]


async def _load_corpus(tenant_id: str, dataset_id: str | None) -> list[dict[str, Any]]:
    # Document has no tenant_id column; tenancy lives on Dataset. Join through.
    async with SessionLocal() as session:
        stmt = (
            select(Chunk.id, Chunk.text)
            .join(Document, Chunk.document_id == Document.id)
            .join(Dataset, Document.dataset_id == Dataset.id)
            .where(Dataset.tenant_id == _uuid(tenant_id), Chunk.parent_id.is_(None))
        )
        if dataset_id:
            stmt = stmt.where(Document.dataset_id == _uuid(dataset_id))
        res = await session.execute(stmt)
        return [{"id": r[0], "text": r[1]} for r in res.all()]


def _uuid(s: str):
    import uuid

    return uuid.UUID(s)


def rrf_fusion(
    dense: list[tuple[str, float]],
    sparse: list[tuple[str, float]],
    k: int | None = None,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion — score = sum(1 / (k + rank)). Score-scale
    agnostic, which is why it works across dense (cosine) and sparse (BM25)."""
    k = k or settings.rrf_k
    scores: dict[str, float] = {}
    for rank, (doc_id, _) in enumerate(sorted(dense, key=lambda x: x[1], reverse=True), start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    for rank, (doc_id, _) in enumerate(sorted(sparse, key=lambda x: x[1], reverse=True), start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
