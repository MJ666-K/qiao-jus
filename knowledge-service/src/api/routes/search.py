from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
import json

from api.deps import CurrentUserDep, SessionDep
from core.llm import chat, stream_chat
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
        graph_ctx = await _graph_context(
            payload.query, user.tenant_id, payload.dataset_id
        )
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
        graph_strs = [
            f"{g['name']}({g.get('type','')})"
            for g in graph_ctx[:5]
            if isinstance(g, dict)
        ]
        context_blocks.append("知识图谱关联实体：" + " | ".join(graph_strs))
    context = "\n\n".join(context_blocks) or "（无相关上下文）"

    messages = [
        {
            "role": "system",
            "content": "你是知识库问答助手。严格依据上下文作答，并标注来源；若上下文不足请明确说明。",
        },
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


@router.post("/answer/stream")
async def answer_stream(payload: SearchQuery, user: CurrentUserDep):
    """流式问答接口，使用 SSE (Server-Sent Events) 返回实时生成的答案。

    流程：
    1. 先发送检索结果和图谱实体（一次性）
    2. 然后流式发送 LLM 生成的答案
    3. 最后发送完成标记
    """
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
        graph_strs = [
            f"{g['name']}({g.get('type','')})"
            for g in graph_ctx[:5]
            if isinstance(g, dict)
        ]
        context_blocks.append("知识图谱关联实体：" + " | ".join(graph_strs))
    context = "\n\n".join(context_blocks) or "（无相关上下文）"

    messages = [
        {
            "role": "system",
            "content": "你是知识库问答助手。严格依据上下文作答，并标注来源；若上下文不足请明确说明。",
        },
        {"role": "user", "content": f"问题：{payload.query}\n\n上下文：\n{context}"},
    ]

    async def generate():
        sources = [SearchHit(**h) for h in hits]
        graph_entities = [g.get("name", "") for g in graph_ctx if isinstance(g, dict)]
        init_data = {
            "type": "init",
            "query": payload.query,
            "sources": [s.model_dump(mode="json") for s in sources],
            "graph_entities": graph_entities,
        }
        yield f"data: {json.dumps(init_data, ensure_ascii=False)}\n\n"

        try:
            async for chunk in stream_chat(messages):
                yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            return

        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _graph_context(query: str, tenant_id: str, dataset_id) -> list[dict]:
    try:
        ds = str(dataset_id) if dataset_id else None
        res = await resolve_graph_entities(
            query, tenant_id, depth=2, limit=20, dataset_id=ds
        )
    except Exception:
        return []
    entities = res.get("entities", []) if res else []
    return [
        {
            "name": e.get("name"),
            "type": e.get("type"),
            "description": e.get("description"),
        }
        for e in entities
    ]
