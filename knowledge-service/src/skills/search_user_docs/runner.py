from typing import Any

from sqlalchemy import select

from models.base import Chunk, Dataset, Document
from retrieve.hybrid import retrieve_children
from skills.base import Skill
from storage.postgres import SessionLocal


class SearchUserDocsSkill(Skill):
    name = "search_user_docs"
    description = "Search user-private documents (contract/dispute) within tenant"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        tenant_id = params["tenant_id"]
        doc_types = params.get("doc_types") or ["contract", "dispute", "report"]
        if isinstance(doc_types, str):
            doc_types = [doc_types]

        hits = []
        for dt in doc_types:
            h = await retrieve_children(
                query=params["query"],
                tenant_id=tenant_id,
                doc_type=dt,
                top_k=params.get("top_k", 4),
            )
            hits.extend(h)

        async with SessionLocal() as session:
            doc_ids = {h.get("document_id") for h in hits if h.get("document_id")}
            title_map: dict[str, str] = {}
            if doc_ids:
                res = await session.execute(
                    select(Document.id, Document.title, Document.metadata_).where(Document.id.in_(doc_ids))
                )
                for row in res.all():
                    title_map[str(row[0])] = {
                        "title": row[1],
                        "doc_type": (row[2] or {}).get("doc_type", "user_doc"),
                    }

        for h in hits:
            doc_id = h.get("document_id")
            info = title_map.get(doc_id, {}) if doc_id else {}
            h["source_type"] = "user_doc"
            h["source_title"] = info.get("title") or "用户材料"
        return {"hits": hits, "count": len(hits)}
