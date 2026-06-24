from __future__ import annotations

from typing import Any

from pipeline.graph_build import extract_entities_relations
from retrieve.hybrid import retrieve_children
from storage.neo4j_client import local_query, local_query_by_chunks, fetch_relations_among


async def resolve_graph_entities(
    query: str,
    tenant_id: str,
    depth: int = 2,
    limit: int = 50,
    hits: list[dict] | None = None,
) -> dict[str, Any]:
    """Match graph entities by keyword, then fall back to chunk-linked entities.

    Args:
        query: 用户查询
        tenant_id: 租户ID
        depth: 遍历深度
        limit: 结果限制
        hits: 可选的检索结果，避免重复调用 retrieve_children
    """
    q = query.strip()
    if not q:
        return {"entities": [], "chunks": [], "relations": []}

    res = await local_query([], tenant_id=tenant_id, depth=depth, limit=limit, keywords=[q])
    if res.get("entities"):
        return res

    ents, _ = await extract_entities_relations(q)
    names = [e["name"] for e in ents]
    keywords = names + [q]
    res = await local_query(
        names,
        tenant_id=tenant_id,
        depth=depth,
        limit=limit,
        keywords=keywords,
    )
    if not res.get("entities"):
        if hits is None:
            hits = await retrieve_children(query=q, tenant_id=tenant_id, top_k=8)
        chunk_ids = [h["chunk_id"] for h in hits if h.get("chunk_id")]
        if chunk_ids:
            res = await local_query_by_chunks(chunk_ids, tenant_id, depth=depth, limit=limit)
    out = res or {"entities": [], "chunks": [], "relations": []}
    if "relations" not in out:
        ids = [e["id"] for e in out.get("entities", []) if e.get("id")]
        out["relations"] = await fetch_relations_among(ids, tenant_id)
    return out
