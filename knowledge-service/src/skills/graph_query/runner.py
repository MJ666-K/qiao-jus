from typing import Any

from pipeline.graph_query import resolve_graph_entities
from skills.base import Skill


class GraphQuerySkill(Skill):
    """图谱查询 Skill

    Extract entities from query and traverse knowledge graph.
    """

    name = "graph_query"
    description = "Query knowledge graph: extract entities and traverse neighbors"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行图谱查询

        Args:
            params: {
                "query": str,       # 查询字符串
                "tenant_id": str,   # 租户 ID
                "depth": int,       # 遍历深度
                "limit": int,       # 最大结果数
            }

        Returns:
            {
                "entities": list[dict],
                "relations": list[dict],
                "chunks": list[dict],
            }
        """
        result = await resolve_graph_entities(
            query=params["query"],
            tenant_id=params["tenant_id"],
            depth=params.get("depth", 2),
            limit=params.get("limit", 50),
        )
        return result or {"entities": [], "relations": [], "chunks": []}
