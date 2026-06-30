from __future__ import annotations

import asyncio
import logging
import time
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

_retrieve_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_RETRIEVE_TTL = 60


async def retrieve_children(
    query: str,
    tenant_id: str,
    dataset_id: str | None = None,
    doc_type: str | None = None,
    top_k: int | None = None,
    user_id: str | None = None,
    scope: str | None = None,
) -> list[dict[str, Any]]:
    """Hybrid retrieval over child chunks. Combines Qdrant dense search with a
    BM25 sparse index built from current tenant's chunks via Reciprocal Rank
    Fusion. Returns fused, reranked hits with parent context attached.

    When ``user_id`` is given, restricts to that user's private docs (scope=user
    AND user_id matches) PLUS all platform docs (scope=platform). When ``scope``
    is given explicitly ('platform' or 'user'), filters to that scope only.
    
    Results are cached for 60 seconds based on query+tenant_id+filters.
    """
    cache_key = f"{tenant_id}:{query}:{dataset_id}:{doc_type}:{top_k}:{user_id}:{scope}"
    now = time.time()
    cached = _retrieve_cache.get(cache_key)
    if cached and now - cached[0] < _RETRIEVE_TTL:
        logger.info(
            "[RAG] cache hit query=%r tenant=%s hits=%d",
            query[:80],
            tenant_id,
            len(cached[1]),
        )
        return cached[1]

    top_k = top_k or settings.search_top_k
    min_score = settings.retrieval_min_score
    logger.info(
        "[RAG] start query=%r tenant=%s dataset=%s doc_type=%s top_k=%d min_score=%.2f",
        query[:80],
        tenant_id,
        dataset_id,
        doc_type,
        top_k,
        min_score,
    )

    dense_filters: dict[str, Any] = {"tenant_id": tenant_id}
    if dataset_id:
        dense_filters["dataset_id"] = dataset_id
    if doc_type:
        dense_filters["doc_type"] = doc_type
    if scope:
        dense_filters["scope"] = scope
    elif user_id:
        dense_filters["_user_scope"] = user_id

    query_vec = await _embed_query(query)
    logger.info("[RAG] step 1/6 embed query dim=%d", len(query_vec))

    extend = top_k * settings.dense_top_k_multiplier
    dense_task = search_dense(query_vec, dense_filters, extend)
    bm25_task = _bm25_search(query, tenant_id, dataset_id, doc_type, extend)
    dense_hits, bm25_hits = await asyncio.gather(dense_task, bm25_task)

    dense_top = [(h.id, h.score or 0.0) for h in dense_hits[:3]]
    logger.info(
        "[RAG] step 2/6 dense search hits=%d top3=%s",
        len(dense_hits),
        [(str(i)[:8], round(s, 4)) for i, s in dense_top],
    )
    logger.info(
        "[RAG] step 3/6 BM25 search hits=%d top3=%s",
        len(bm25_hits),
        [(i[:8], round(s, 4)) for i, s in bm25_hits[:3]],
    )

    fused = rrf_fusion(
        dense=[(h.id, h.score or 0.0) for h in dense_hits],
        sparse=[(h["id"], h["score"]) for h in bm25_hits],
    )
    logger.info("[RAG] step 4/6 RRF fusion candidates=%d", len(fused))

    if not fused:
        logger.info("[RAG] done: no fused candidates")
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
            "source": _format_source(r),
            "document_id": str(r["document_id"]),
            "page": r.get("page"),
            "metadata": r.get("metadata") or {},
            "doc_type": r.get("doc_type"),
            "article_no": r.get("article_no"),
            "law_name": r.get("law_name"),
            "_raw_pid": pid,
        })

    reranked = await get_reranker().rank(query, candidates, top_k=top_k)
    logger.info(
        "[RAG] step 5/6 rerank in=%d out=%d top3=%s",
        len(candidates),
        len(reranked),
        [
            (r.get("source", "")[:20], round(r.get("_rerank_score", r.get("score", 0)), 4))
            for r in reranked[:3]
        ],
    )

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
            "metadata": r.get("metadata") or {},
            "doc_type": r.get("doc_type"),
            "article_no": r.get("article_no"),
            "law_name": r.get("law_name"),
        })
        if len(out) >= top_k:
            break

    before_filter = len(out)
    out = [r for r in out if r.get("score", 0) >= min_score]
    logger.info(
        "[RAG] step 6/6 score filter min=%.2f: %d -> %d hits",
        min_score,
        before_filter,
        len(out),
    )
    if out:
        logger.info(
            "[RAG] done top hits: %s",
            [(h.get("source", "")[:24], round(h.get("score", 0), 4)) for h in out[:5]],
        )
    else:
        logger.info("[RAG] done: all hits below min_score=%.2f", min_score)

    _retrieve_cache[cache_key] = (now, out)
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
            meta = dict(c.metadata_ or {})
            rows.append({
                "child_id": c.id,
                "child_text": c.text,
                "parent_id": c.parent_id,
                "document_id": c.document_id,
                "title": title,
                "metadata": meta,
                "doc_type": meta.get("doc_type"),
                "article_no": meta.get("article_no"),
                "law_name": meta.get("law_name"),
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


_bm25_cache: dict[tuple[str, str | None, str | None], tuple[float, list[dict[str, Any]], BM25Index]] = {}
_BM25_TTL = 300


async def _get_bm25(tenant_id: str, dataset_id: str | None, doc_type: str | None):
    key = (tenant_id, dataset_id, doc_type)
    now = time.time()
    cached = _bm25_cache.get(key)
    if cached and now - cached[0] < _BM25_TTL:
        return cached[1], cached[2]
    corpus = await _load_corpus(tenant_id, dataset_id, doc_type)
    if not corpus:
        return None
    bm25 = BM25Index(corpus=[c["text"] for c in corpus], k1=settings.bm25_k1, b=settings.bm25_b)
    _bm25_cache[key] = (now, corpus, bm25)
    return corpus, bm25


async def _bm25_search(
    query: str, tenant_id: str, dataset_id: str | None, doc_type: str | None, top_k: int
) -> list[dict[str, Any]]:
    got = await _get_bm25(tenant_id, dataset_id, doc_type)
    if not got:
        return []
    corpus, bm25 = got
    scores = bm25.get_scores(query)
    ranked = sorted(zip(corpus, scores, strict=True), key=lambda x: x[1], reverse=True)[:top_k]
    return [{"id": str(c["id"]), "score": float(s)} for c, s in ranked if s > 0]


_embed_cache: dict[str, tuple[float, list[float]]] = {}
_EMBED_TTL = 600


async def _embed_query(query: str) -> list[float]:
    now = time.time()
    cached = _embed_cache.get(query)
    if cached and now - cached[0] < _EMBED_TTL:
        return cached[1]
    vec = (await asyncio.to_thread(embed_texts, [query]))[0]
    _embed_cache[query] = (now, vec)
    return vec


async def _load_corpus(tenant_id: str, dataset_id: str | None, doc_type: str | None = None) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        stmt = (
            select(Chunk.id, Chunk.text)
            .join(Document, Chunk.document_id == Document.id)
            .join(Dataset, Document.dataset_id == Dataset.id)
            .where(Dataset.tenant_id == _uuid(tenant_id), Chunk.parent_id.is_(None))
        )
        if dataset_id:
            stmt = stmt.where(Document.dataset_id == _uuid(dataset_id))
        if doc_type:
            stmt = stmt.where(Document.metadata_["doc_type"].astext == doc_type)
        res = await session.execute(stmt)
        return [{"id": r[0], "text": r[1]} for r in res.all()]


def _format_source(row: dict[str, Any]) -> str:
    law = row.get("law_name")
    article = row.get("article_no")
    if law and article:
        return f"{law} {article}"
    if row.get("doc_type") == "case":
        cause = (row.get("metadata") or {}).get("cause")
        if cause:
            return f"类案·{cause}"
    return row.get("title") or "未知来源"


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
