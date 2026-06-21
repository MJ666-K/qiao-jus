from typing import Any

from retrieve.hybrid import retrieve_children
from skills.base import Skill


class RagSearchSkill(Skill):
    """RAG 检索 Skill

    Hybrid search combining dense vectors (Qdrant) + sparse (BM25) + RRF fusion.
    """

    name = "rag_search"
    description = "Hybrid RAG retrieval: vector + BM25 + RRF fusion"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行 RAG 检索

        Args:
            params: {
                "query": str,           # 检索查询
                "tenant_id": str,       # 租户 ID
                "dataset_id": str|None, # 数据集过滤（可选）
                "doc_type": str|None,   # 文档类型过滤（可选）
                "top_k": int,           # 返回结果数量
            }

        Returns:
            {
                "hits": list[dict],  # 检索结果
                "count": int,        # 结果数量
            }
        """
        hits = await retrieve_children(
            query=params["query"],
            tenant_id=params["tenant_id"],
            dataset_id=params.get("dataset_id"),
            doc_type=params.get("doc_type"),
            top_k=params.get("top_k", 10),
        )
        return {"hits": hits, "count": len(hits)}
