from typing import Any

from skills.base import Skill


class SearchLawSkill(Skill):
    name = "search_law"
    description = "Search platform law corpus (doc_type=law) for legal articles"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        rag = await self.call_skill("rag_search", {
            "query": params["query"],
            "tenant_id": params["tenant_id"],
            "doc_type": "law",
            "top_k": params.get("top_k", 6),
        })
        hits = rag.get("hits", [])
        for h in hits:
            h["source_type"] = "law"
            h["source_title"] = h.get("source") or f"{h.get('law_name') or ''} {h.get('article_no') or ''}".strip()
        return {"hits": hits, "count": len(hits)}
