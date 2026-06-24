import asyncio
from typing import Any

from core.llm import chat
from skills.base import Skill


class QASkill(Skill):
    """问答 Skill

    Combines RAG retrieval + Graph context + LLM generation.
    支持组合调用其他 Skill（rag_search, graph_query）。
    """

    name = "qa"
    description = "Question answering with RAG + Graph context + LLM"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行问答

        Args:
            params: {
                "query": str,       # 用户问题
                "tenant_id": str,   # 租户 ID
                "use_graph": bool,  # 是否使用图谱上下文
                "top_k": int,       # 检索数量
            }

        Returns:
            {
                "query": str,
                "answer": str,
                "sources": list[dict],
                "graph_entities": list[dict],
            }
        """
        query = params["query"]
        tenant_id = params["tenant_id"]
        use_graph = params.get("use_graph", True)

        if use_graph:
            rag_task = self.call_skill("rag_search", {
                "query": query,
                "tenant_id": tenant_id,
                "top_k": params.get("top_k", 8),
            })
            graph_task = self.call_skill("graph_query", {
                "query": query,
                "tenant_id": tenant_id,
                "depth": 2,
            })
            rag_result, graph_result = await asyncio.gather(rag_task, graph_task)
            graph_ctx = graph_result.get("entities", [])
        else:
            rag_result = await self.call_skill("rag_search", {
                "query": query,
                "tenant_id": tenant_id,
                "top_k": params.get("top_k", 8),
            })
            graph_ctx = []

        hits = rag_result.get("hits", [])
        context_blocks = [h["text"] for h in hits[:6]]
        if graph_ctx:
            graph_strs = [
                f"{g.get('name', '')}({g.get('type', '')})"
                for g in graph_ctx[:5]
                if isinstance(g, dict)
            ]
            context_blocks.append("知识图谱关联：" + " | ".join(graph_strs))
        context = "\n\n".join(context_blocks) or "（无相关上下文）"

        messages = [
            {
                "role": "system",
                "content": "你是知识库问答助手。严格依据上下文作答，标注来源。",
            },
            {
                "role": "user",
                "content": f"问题：{query}\n\n上下文：\n{context}",
            },
        ]
        answer = chat(messages)

        return {
            "query": query,
            "answer": answer,
            "sources": hits,
            "graph_entities": graph_ctx,
        }
