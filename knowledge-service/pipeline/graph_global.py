from __future__ import annotations

import logging
from typing import Any

from core.llm import chat, chat_json
from storage.neo4j_client import list_communities_async

logger = logging.getLogger(__name__)


async def global_answer(query: str, tenant_id: str, top_communities: int = 5) -> dict[str, Any]:
    """GraphRAG-style global QA: rank communities by query relevance, ask each
    for a partial answer, then reduce to a final answer. Best for abstract /
    cross-document questions ("整体战略", "主要格局") that local retrieval misses."""
    communities = await list_communities_async(tenant_id, level=0)
    if not communities:
        return {"answer": "(知识图谱暂无社区摘要，请先调用 /graph/rebuild)", "communities_used": 0}

    # Stage 1: rank communities by query relevance via LLM
    ranked = await _rank_communities(query, communities, top_communities)

    # Stage 2: map - each ranked community produces a partial answer
    partials: list[dict[str, Any]] = []
    for cm in ranked:
        try:
            partial = await _community_partial_answer(query, cm)
            partials.append({"community_id": cm["id"], "title": cm["title"], "partial": partial})
        except Exception as e:
            logger.warning("community %s partial failed: %s", cm.get("id"), e)

    if not partials:
        return {"answer": "(社区问答生成失败)", "communities_used": 0}

    # Stage 3: reduce - synthesize final answer from partials
    final = _reduce_partials(query, partials)
    return {
        "answer": final,
        "communities_used": len(partials),
        "community_refs": [
            {"title": p["title"], "partial_excerpt": p["partial"][:120]}
            for p in partials
        ],
    }


async def _rank_communities(
    query: str, communities: list[dict[str, Any]], top_n: int
) -> list[dict[str, Any]]:
    # Use titles/summaries as compact proxy; LLM picks most relevant N.
    items = [
        {"id": str(i), "title": cm.get("title", ""), "summary": (cm.get("summary") or "")[:150]}
        for i, cm in enumerate(communities)
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "你从一组知识图谱社区摘要中挑选与问题最相关的若干个。"
                "输出 JSON。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"问题：{query}\n\n社区：\n{items}\n\n"
                f'挑选最相关的 {top_n} 个。输出：{{"ids":["0","3",...]}}'
            ),
        },
    ]
    data = await _call_chat_json_async(messages)
    picked_ids = set(data.get("ids", [])[:top_n])
    return [communities[i] for i in range(len(communities)) if str(i) in picked_ids] or communities[:top_n]


async def _community_partial_answer(query: str, cm: dict[str, Any]) -> str:
    summary = cm.get("summary") or ""
    messages = [
        {
            "role": "system",
            "content": "你是知识库问答助手。基于给定的社区摘要，回答用户问题；若摘要不足以回答，明确说明。中文回答 100-200 字。",
        },
        {"role": "user", "content": f"问题：{query}\n\n社区摘要：{summary}"},
    ]
    return await _call_chat_async(messages)


def _reduce_partials(query: str, partials: list[dict[str, Any]]) -> str:
    parts_text = "\n\n".join(
        f"[{i+1}] {p['title']}：{p['partial']}" for i, p in enumerate(partials)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你是综合分析师。给定来自多个知识图谱社区的局部回答，"
                "综合出对用户问题的最终回答。中文 200-400 字，结尾标注引用编号 [1] [2] 等。"
            ),
        },
        {"role": "user", "content": f"问题：{query}\n\n局部回答：\n{parts_text}"},
    ]
    try:
        return chat(messages)
    except Exception as e:
        logger.warning("reduce failed: %s", e)
        return "\n\n".join(p["partial"] for p in partials)


async def _call_chat_async(messages: list[dict[str, str]]) -> str:
    import asyncio

    return await asyncio.to_thread(chat, messages)


async def _call_chat_json_async(messages: list[dict[str, str]]) -> dict[str, Any]:
    import asyncio

    return await asyncio.to_thread(chat_json, messages)
