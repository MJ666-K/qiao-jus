from __future__ import annotations

import logging
from typing import Any

from core.llm import chat_json

logger = logging.getLogger(__name__)


class Reranker:
    """LLM-based cross-encoder reranker. Uses the same LLM provider as the rest
    of the stack (DashScope/ZhipuAI/etc) — no model download needed. Falls back
    to original order if the LLM call fails."""

    async def rank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        if len(candidates) == 1:
            return candidates[: (top_k or len(candidates))]

        scored = await self._score_batch(query, candidates)
        scored.sort(key=lambda x: x.get("_rerank_score", 0.5), reverse=True)
        return scored[: (top_k or len(candidates))]

    async def _score_batch(
        self, query: str, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        try:
            return await self._llm_score(query, candidates)
        except Exception as e:
            logger.warning("LLM reranker failed, keeping original order: %s", e)
            return [dict(c, _rerank_score=0.5) for c in candidates]

    async def _llm_score(
        self, query: str, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # Pack candidates into one LLM call. Returns scores[id] in [0,1].
        items = [
            {"id": str(i), "text": (c.get("text") or "")[:300]}
            for i, c in enumerate(candidates)
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "你是相关性打分器。为每个候选打 0-1 分（1=完全相关，0=无关）。"
                    "输出严格 JSON。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"问题：{query}\n\n候选：\n{items}\n\n"
                    '输出：{"scores":[{"id":"0","score":0.92}]}'
                ),
            },
        ]
        data = await _call_chat_json_async(messages)
        score_map: dict[str, float] = {}
        for s in data.get("scores", []):
            try:
                score_map[str(s["id"])] = float(s["score"])
            except (KeyError, ValueError, TypeError):
                continue

        return [dict(c, _rerank_score=score_map.get(str(i), 0.5)) for i, c in enumerate(candidates)]


class PassThroughReranker(Reranker):
    """No-op reranker — keeps input order. Use when LLM rerank is too slow."""

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


async def _call_chat_json_async(messages: list[dict[str, str]]) -> dict[str, Any]:
    import asyncio

    return await asyncio.to_thread(chat_json, messages)
