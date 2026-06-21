from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from api.deps import get_current_user  # noqa: F401  (re-exported for tests)
from core.tenant import CurrentUser
from skills import load_skills
from skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

mcp = FastMCP("knowledge")

# 加载所有 Skills
load_skills()


async def _resolve_user(token: str | None) -> CurrentUser:
    """MCP callers pass a JWT via the `__user_token__` argument; we translate it
    into a CurrentUser so the same tenancy rules apply as in REST routes."""
    if not token:
        raise PermissionError("missing user token")
    from core.security import decode_token
    payload = decode_token(token)
    return CurrentUser(
        user_id=payload["sub"],
        tenant_id=payload["tenant_id"],
        scopes=tuple(payload.get("scopes", [])),
    )


def _skill_tool_wrapper(skill_name: str):
    """创建 Skill tool 的包装函数"""
    async def skill_tool(
        query: str,
        tenant_id: str,
        depth: int = 2,
        top_k: int = 10,
        use_graph: bool = True,
        user_token: str | None = None,
        dataset_id: str | None = None,
        doc_type: str | None = None,
    ) -> dict[str, Any]:
        """Dynamic Skill tool wrapper"""
        user = await _resolve_user(user_token)
        skill = SkillRegistry.get(skill_name)
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")
        params = {
            "query": query,
            "tenant_id": user.tenant_id,
            "depth": depth,
            "top_k": top_k,
            "use_graph": use_graph,
            "dataset_id": dataset_id,
            "doc_type": doc_type,
        }
        return await skill.execute(params)
    return skill_tool


# 动态注册 Skill tools
for skill_meta in SkillRegistry.list_skills():
    skill_name = skill_meta["name"]
    tool_fn = _skill_tool_wrapper(skill_name)
    tool_fn.__name__ = f"{skill_name}_tool"
    tool_fn.__doc__ = f"Execute {skill_name} skill"
    mcp.tool()(tool_fn)


# ==================== 原有 Tools（保持向后兼容） ====================

@mcp.tool()
async def knowledge_search(
    query: str,
    top_k: int = 10,
    dataset_id: str | None = None,
    user_token: str | None = None,
) -> dict[str, Any]:
    """Search the knowledge base (hybrid vector + BM25 + parent-context).

    Returns up to `top_k` relevant chunks with source attribution.
    Pass a valid JWT in `user_token` for tenant isolation.
    """
    from retrieve.hybrid import retrieve_children

    user = await _resolve_user(user_token)
    hits = await retrieve_children(
        query=query,
        tenant_id=user.tenant_id,
        dataset_id=dataset_id,
        top_k=top_k,
    )
    return {"query": query, "count": len(hits), "hits": hits}


@mcp.tool()
async def graph_query(
    query: str,
    depth: int = 2,
    user_token: str | None = None,
) -> dict[str, Any]:
    """Query the knowledge graph: extract entities from the query, traverse
    neighbors up to `depth` hops, return entities + related chunks.
    """
    from pipeline.graph_build import extract_entities_relations
    from storage.neo4j_client import local_query

    user = await _resolve_user(user_token)
    ents, _ = await extract_entities_relations(query)
    if not ents:
        return {"entities": [], "chunks": []}
    res = await local_query(
        [e["name"] for e in ents], tenant_id=user.tenant_id, depth=depth, limit=50
    )
    return res or {"entities": [], "chunks": []}


@mcp.tool()
async def knowledge_answer(
    query: str,
    use_graph: bool = True,
    user_token: str | None = None,
) -> dict[str, Any]:
    """One-shot QA: hybrid retrieval (+ optional graph context) + LLM answer
    with citations. Pass a valid JWT in `user_token` for tenant isolation."""
    from core.llm import chat
    from pipeline.graph_build import extract_entities_relations
    from retrieve.hybrid import retrieve_children
    from storage.neo4j_client import local_query

    user = await _resolve_user(user_token)
    hits = await retrieve_children(query=query, tenant_id=user.tenant_id, top_k=8)
    graph_ctx: list[dict] = []
    if use_graph:
        ents, _ = await extract_entities_relations(query)
        if ents:
            res = await local_query(
                [e["name"] for e in ents], tenant_id=user.tenant_id, depth=2, limit=20
            )
            graph_ctx = (res or {}).get("entities", [])

    context = "\n\n".join(h["text"] for h in hits[:6])
    if graph_ctx:
        context += "\n\n图谱关联：" + " | ".join(g.get("name", "") for g in graph_ctx[:5])
    if not context.strip():
        context = "（无相关上下文）"

    messages = [
        {"role": "system", "content": "你是知识库问答助手。严格依据上下文作答，标注来源。"},
        {"role": "user", "content": f"问题：{query}\n\n上下文：\n{context}"},
    ]
    text = chat(messages)
    return {"query": query, "answer": text, "sources": hits, "graph_entities": graph_ctx}


@mcp.tool()
async def knowledge_global_answer(
    query: str,
    user_token: str | None = None,
) -> dict[str, Any]:
    """GraphRAG global QA: best for abstract / cross-document questions
    ("整体战略", "主要格局"). Map-reduces over community summaries.
    Requires communities to be built (POST /graph/rebuild)."""
    from pipeline.graph_global import global_answer

    user = await _resolve_user(user_token)
    return await global_answer(query, user.tenant_id)


def run_stdio() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio()
