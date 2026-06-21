from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Any

from core.llm import chat_json
from storage.neo4j_client import (
    sync_fetch_entity_graph,
    sync_write_communities,
)

logger = logging.getLogger(__name__)

# Min entities per community to bother summarizing; below this the community
# is too small to carry meaningful global knowledge.
MIN_COMMUNITY_SIZE = 2
MAX_COMMUNITIES_TO_SUMMARIZE = 30


def detect_and_write_communities(tenant_id: str) -> dict[str, Any]:
    """Run community detection on the tenant's entity graph and persist results.

    Uses a label-propagation-style algorithm via networkx. Fast, deterministic
    enough, and avoids needing the Neo4j GDS plugin (which is enterprise-only).
    Returns {"communities": N, "entities_covered": N}."""
    try:
        import networkx as nx
    except ImportError:
        logger.warning("networkx not installed; skipping community detection")
        return {"communities": 0, "entities_covered": 0}

    data = sync_fetch_entity_graph(tenant_id)
    if not data["entities"]:
        return {"communities": 0, "entities_covered": 0}

    g = nx.Graph()
    for e in data["entities"]:
        g.add_node(e["id"], **e)
    for src, tgt in data["relations"]:
        if g.has_node(src) and g.has_node(tgt):
            g.add_edge(src, tgt)

    # Label propagation: fast, gives natural communities without a fixed K
    try:
        communities_gen = nx.algorithms.community.asyn_lpa_communities(g, seed=42)
        raw_communities = [list(c) for c in communities_gen]
    except Exception as e:
        logger.warning("community detection failed: %s", e)
        raw_communities = [list(g.nodes())]

    communities_to_write: list[dict[str, Any]] = []
    node_lookup = {e["id"]: e for e in data["entities"]}
    for entity_ids in raw_communities:
        if len(entity_ids) < MIN_COMMUNITY_SIZE:
            continue
        names = sorted({node_lookup[eid]["name"] for eid in entity_ids if eid in node_lookup})
        cm_id = str(uuid.uuid4())
        communities_to_write.append({
            "id": cm_id,
            "level": 0,
            "entities": entity_ids,
            "title": " / ".join(names[:5]) + ("..." if len(names) > 5 else ""),
            "_names": names,
        })

    communities_to_write = communities_to_write[:MAX_COMMUNITIES_TO_SUMMARIZE]
    if not communities_to_write:
        return {"communities": 0, "entities_covered": 0}

    for cm in communities_to_write:
        cm["summary"] = _summarize_community(cm["_names"], cm["entities"], node_lookup)

    cleaned = [
        {"id": cm["id"], "level": cm["level"], "entities": cm["entities"],
         "summary": cm["summary"], "title": cm["title"]}
        for cm in communities_to_write
    ]
    sync_write_communities(tenant_id, cleaned)
    return {
        "communities": len(cleaned),
        "entities_covered": sum(len(cm["entities"]) for cm in cleaned),
    }


def _summarize_community(
    names: list[str], entity_ids: list[str], node_lookup: dict[str, dict[str, Any]]
) -> str:
    if not names:
        return ""
    # Collect short descriptions of up to 10 entities for context
    desc_lines = []
    for eid in entity_ids[:10]:
        e = node_lookup.get(eid)
        if not e:
            continue
        desc_lines.append(f"- {e['name']}（{e.get('type', '')}）")
    desc_text = "\n".join(desc_lines)
    messages = [
        {
            "role": "system",
            "content": (
                "你是知识图谱社区摘要生成器。"
                "给定一组相关实体，生成 100-200 字的综合描述，"
                "说明这组实体共同描述了什么主题/概念。输出严格 JSON。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"实体列表：\n{desc_text}\n\n"
                '输出：{"summary":"..."}'
            ),
        },
    ]
    try:
        data = chat_json(messages)
        return str(data.get("summary", ""))[:500]
    except Exception as e:
        logger.warning("community summary failed: %s", e)
        return f"包含实体：{', '.join(names[:5])}"