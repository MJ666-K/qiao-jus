from typing import Any

from skills.base import Skill


class SearchCaseSkill(Skill):
    name = "search_case"
    description = "Search platform case corpus (doc_type=case) for precedent rulings"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        rag = await self.call_skill("rag_search", {
            "query": params["query"],
            "tenant_id": params["tenant_id"],
            "doc_type": "case",
            "top_k": params.get("top_k", 5),
        })
        hits = rag.get("hits", [])
        for h in hits:
            h["source_type"] = "case"
            meta = h.get("metadata") or {}
            h["source_title"] = h.get("source") or f"类案·{meta.get('cause') or '相关判例'}"
        return {"hits": hits, "count": len(hits)}
