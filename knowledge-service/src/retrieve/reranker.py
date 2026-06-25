from __future__ import annotations

import logging
from typing import Any

from core.llm import rerank_documents

logger = logging.getLogger(__name__)

# Per-document char cap sent to rerank API (avoid oversized payloads).
_MAX_DOC_CHARS = 8000


class Reranker:
    """DashScope qwen3-rerank via compatible-api/v1/reranks."""

    async def rank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        if len(candidates) == 1:
            return [dict(candidates[0], _rerank_score=candidates[0].get("score", 1.0))]

        limit = top_k or len(candidates)
        try:
            return await self._api_rank(query, candidates, limit)
        except Exception as e:
            logger.warning("Rerank API failed, keeping RRF order: %s", e)
            return candidates[:limit]

    async def _api_rank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        documents = [(c.get("text") or "")[:_MAX_DOC_CHARS] for c in candidates]
        ranked = await rerank_documents(query, documents, top_n=top_k)

        out: list[dict[str, Any]] = []
        seen: set[int] = set()
        for idx, score in ranked:
            if idx in seen or idx < 0 or idx >= len(candidates):
                continue
            seen.add(idx)
            out.append(dict(candidates[idx], _rerank_score=score))

        if len(out) < top_k:
            for i, c in enumerate(candidates):
                if i in seen:
                    continue
                out.append(dict(c, _rerank_score=c.get("score", 0.0)))
                if len(out) >= top_k:
                    break
        return out[:top_k]


class PassThroughReranker(Reranker):
    """No-op reranker — keeps input order."""

    async def rank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        return candidates[: (top_k or len(candidates))]


_default: Reranker | None = None


def get_reranker() -> Reranker:
    global _default
    if _default is None:
        _default = Reranker()
    return _default


def set_reranker(r: Reranker) -> None:
    global _default
    _default = r
