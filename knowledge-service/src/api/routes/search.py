from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from api.deps import CurrentUserDep, SessionDep
from core.llm import chat
from pipeline.graph_query import resolve_graph_entities
from retrieve.hybrid import retrieve_children
from schemas.search import AnswerResult, SearchHit, SearchQuery, SearchResult

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResult)
async def search(payload: SearchQuery, user: CurrentUserDep):
    hits = await retrieve_children(
        query=payload.query,
        tenant_id=user.tenant_id,
        dataset_id=str(payload.dataset_id) if payload.dataset_id else None,
        doc_type=payload.doc_type,
        top_k=payload.top_k,
    )
    graph_ctx = []
    if payload.use_graph:
        graph_ctx = await _graph_context(payload.query, user.tenant_id, payload.dataset_id)
    return SearchResult(
        query=payload.query,
        hits=[SearchHit(**h) for h in hits],
        graph_context=graph_ctx,
    )


@router.post("/answer", response_model=AnswerResult)
async def answer(payload: SearchQuery, user: CurrentUserDep):
    hits = await retrieve_children(
        query=payload.query,
        tenant_id=user.tenant_id,
        dataset_id=str(payload.dataset_id) if payload.dataset_id else None,
        doc_type=payload.doc_type,
        top_k=payload.top_k,
    )
    graph_ctx = await _graph_context(payload.query, user.tenant_id, payload.dataset_id)

    context_blocks = [h["text"] for h in hits[:6]]
    if graph_ctx:
        graph_strs = [f"{g['name']}({g.get('type','')})" for g in graph_ctx[:5] if isinstance(g, dict)]
        context_blocks.append("知识图谱关联实体：" + " | ".join(graph_strs))
    context = "\n\n".join(context_blocks) or "（无相关上下文）"

    messages = [
        {"role": "system", "content": "你是知识库问答助手。严格依据上下文作答，并标注来源；若上下文不足请明确说明。"},
        {"role": "user", "content": f"问题：{payload.query}\n\n上下文：\n{context}"},
    ]
    try:
        text = chat(messages)
    except Exception as e:
        raise HTTPException(500, f"LLM error: {e}") from e

    return AnswerResult(
        query=payload.query,
        answer=text,
        sources=[SearchHit(**h) for h in hits],
        graph_entities=[g.get("name", "") for g in graph_ctx if isinstance(g, dict)],
    )


async def _graph_context(query: str, tenant_id: str, dataset_id) -> list[dict]:
    try:
        res = await resolve_graph_entities(query, tenant_id, depth=2, limit=20)
    except Exception:
        return []
    entities = res.get("entities", []) if res else []
    return [{"name": e.get("name"), "type": e.get("type"), "description": e.get("description")} for e in entities]
