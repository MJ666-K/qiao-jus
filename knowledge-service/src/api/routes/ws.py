import asyncio
import json
import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from core.llm import stream_chat, chat
from core.security import TokenError, decode_token
from core.tenant import CurrentUser, set_current_user
from models.base import (
    Assistant,
    Conversation,
    Message,
    MessageCitation,
    Report,
    User,
)
from retrieve.hybrid import retrieve_children
from schemas.search import Citation
from skills import load_skills
from storage.postgres import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])

HISTORY_TURNS = 10
TOP_K_RETRIEVAL = 8
MIN_RETRIEVAL_SCORE = 0.15


def _uuid(s: str) -> uuid.UUID:
    return uuid.UUID(s)


@router.websocket("/ws/chat")
async def ws_chat(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_token(token)
    except TokenError as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(e))
        return
    if payload.get("type") != "access":
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="not access token"
        )
        return

    user_id = payload["sub"]
    tenant_id = payload["tenant_id"]
    set_current_user(
        CurrentUser(
            user_id=user_id,
            tenant_id=tenant_id,
            scopes=tuple(payload.get("scopes") or []),
        )
    )

    async with SessionLocal() as session:
        user = await session.get(User, _uuid(user_id))
        if not user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="user not found"
            )
            return

    await websocket.accept()
    load_skills()

    conversation: Conversation | None = None
    stop_event = asyncio.Event()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, "invalid json")
                continue

            mtype = msg.get("type")
            if mtype == "init":
                conversation = await _init_or_restore_conversation(
                    websocket, user_id, tenant_id, msg
                )
                continue
            if mtype == "stop":
                stop_event.set()
                continue
            if mtype == "message":
                if not conversation:
                    await _send_error(websocket, "init required before message")
                    continue
                content = (msg.get("content") or "").strip()
                if not content:
                    await _send_error(websocket, "empty content")
                    continue
                stop_event.clear()
                await _handle_message(
                    websocket,
                    conversation,
                    content,
                    tenant_id,
                    stop_event,
                    user_id,
                )
                continue
            await _send_error(websocket, f"unknown message type: {mtype}")
    except WebSocketDisconnect:
        logger.info("WS disconnected user=%s", user_id)
    except Exception:
        logger.exception("WS handler crashed")


async def _init_or_restore_conversation(
    ws: WebSocket, user_id: str, tenant_id: str, msg: dict[str, Any]
) -> Conversation | None:
    conv_id = msg.get("conversation_id")
    if not conv_id:
        await _send_error(ws, "conversation_id required")
        return None
    async with SessionLocal() as s:
        conv = await s.get(Conversation, _uuid(conv_id))
        if not conv or str(conv.tenant_id) != tenant_id:
            await _send_error(ws, "conversation not found")
            return None
        if not conv.assistant_id:
            await _send_error(ws, "conversation has no assistant")
            return None
    await ws.send_json(
        {
            "type": "connected",
            "session_id": str(conv.id),
            "assistant_id": str(conv.assistant_id),
        }
    )
    return conv


async def _load_assistant_bindings(conv: Conversation) -> tuple[list[str], list[str], bool]:
    if not conv.assistant_id:
        return [], [], True
    async with SessionLocal() as s:
        assistant = await s.get(Assistant, conv.assistant_id)
        if not assistant:
            return [], [], True
        dataset_ids = [str(x) for x in (assistant.dataset_ids or []) if x]
        report_ids = [str(x) for x in (assistant.report_ids or []) if x]
        return dataset_ids, report_ids, assistant.enable_thinking


async def _handle_message(
    ws: WebSocket,
    conv: Conversation,
    user_content: str,
    tenant_id: str,
    stop_event: asyncio.Event,
    user_id: str | None = None,
) -> None:
    async with SessionLocal() as s:
        fresh = await s.get(Conversation, conv.id)
        if fresh:
            conv = fresh

    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=user_content,
    )
    async with SessionLocal() as s:
        s.add(user_msg)
        await s.commit()
        await s.refresh(user_msg)
        history_rows = await _load_history(s, conv.id, HISTORY_TURNS)

    dataset_ids, report_ids, _assistant_thinking = await _load_assistant_bindings(conv)
    has_rag = bool(dataset_ids) or bool(report_ids)

    await ws.send_json({"type": "status", "content": "思考中..."})
    citations = await _gather_citations(
        user_content, tenant_id, report_ids, user_id, dataset_ids
    )
    report_context = (
        await _load_reports_context(report_ids, tenant_id) if report_ids else ""
    )

    history_msgs = _format_history(history_rows)
    if has_rag:
        sys_prompt = _system_prompt(bool(report_ids), rag_mode=True)
        context_block = _context_block(citations, report_context)
        user_payload = (
            f"{user_content}\n\n{context_block}" if context_block else user_content
        )
    else:
        sys_prompt = _system_prompt(False, rag_mode=False)
        user_payload = user_content

    messages = [
        {"role": "system", "content": sys_prompt},
        *history_msgs,
        {"role": "user", "content": user_payload},
    ]

    await ws.send_json({"type": "status", "content": "生成中..."})

    streamed_text: list[str] = []
    suggested: list[str] = []
    try:
        async for chunk in stream_chat(messages, temperature=0.4):
            if stop_event.is_set():
                break
            streamed_text.append(chunk)
            await ws.send_json({"type": "token", "content": chunk})
    except Exception as e:
        await _send_error(ws, f"LLM stream failed: {e}")
        return

    answer = "".join(streamed_text).strip()
    if not answer:
        await _send_error(ws, "empty LLM output")
        return

    sug_prompt = [
        {
            "role": "system",
            "content": "你是一个法律问答助手。根据用户的问题和助手的回答，生成3个用户可能追问的简短问题。用分号分隔，只输出问题内容，不要有前缀标记。",
        },
        {"role": "user", "content": f"用户问题：{user_content}\n\n助手回答：{answer}"},
    ]
    try:
        suggested_text = chat(sug_prompt, temperature=0.3)
        if suggested_text:
            raw_qs = suggested_text.strip()
            suggested = []
            for q in re.split(r"[;；]", raw_qs):
                q = q.strip()
                q = re.sub(r"^Q\d+[.:：\s]+", "", q)
                q = re.sub(r"^[上下中][.。：\s]+", "", q)
                if q:
                    suggested.append(q)
            suggested = suggested[:3]
    except Exception as e:
        logger.warning(f"Failed to generate suggested questions: {e}")

    cit_payload = [c.model_dump(mode="json") for c in citations]
    asst_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=answer,
        confidence=0,
        suggested_questions=suggested,
        citations_json=cit_payload,
    )
    async with SessionLocal() as s:
        s.add(asst_msg)
        await s.flush()
        for c in citations:
            s.add(
                MessageCitation(
                    message_id=asst_msg.id,
                    chunk_id=uuid.UUID(c.chunk_id) if c.chunk_id else None,
                    document_id=uuid.UUID(c.document_id) if c.document_id else None,
                    source_type=c.source_type,
                    source_title=c.source_title,
                    excerpt=c.excerpt,
                    page=c.page,
                )
            )
        await s.commit()

    await ws.send_json(
        {
            "type": "done",
            "message_id": str(asst_msg.id),
            "content": answer,
            "confidence": 0,
            "citations": cit_payload,
            "suggested_questions": suggested,
        }
    )


async def _gather_citations(
    query: str,
    tenant_id: str,
    report_ids: list[str],
    user_id: str | None = None,
    dataset_ids: list[str] | None = None,
) -> list[Citation]:
    out: list[Citation] = []
    ids = [d for d in (dataset_ids or []) if d]
    rids = [r for r in (report_ids or []) if r]

    if not ids and not rids:
        return []

    for ds_id in ids:
        hits = await retrieve_children(
            query=query,
            tenant_id=tenant_id,
            dataset_id=ds_id,
            top_k=TOP_K_RETRIEVAL,
            user_id=user_id,
        )
        for h in hits:
            if h.get("score", 0) < MIN_RETRIEVAL_SCORE:
                continue
            dt = h.get("doc_type") or "user_doc"
            st = "law" if dt == "law" else "case" if dt == "case" else "user_doc"
            if dt == "compliance":
                st = "compliance"
            out.append(
                Citation(
                    chunk_id=h.get("chunk_id"),
                    document_id=h.get("document_id"),
                    source_type=st,
                    source_title=h.get("source") or "知识库",
                    excerpt=(h.get("text") or "")[:280],
                    page=h.get("page"),
                    score=h.get("score"),
                )
            )

    if rids and user_id:
        report_hits = await retrieve_children(
            query=query,
            tenant_id=tenant_id,
            doc_type="report",
            top_k=3,
            user_id=user_id,
        )
        for h in report_hits:
            if h.get("score", 0) < MIN_RETRIEVAL_SCORE:
                continue
            out.append(
                Citation(
                    chunk_id=h.get("chunk_id"),
                    document_id=h.get("document_id"),
                    source_type="report",
                    source_title=h.get("source") or "用户报告",
                    excerpt=(h.get("text") or "")[:280],
                    page=h.get("page"),
                    score=h.get("score"),
                )
            )

    seen: set[str] = set()
    deduped: list[Citation] = []
    for c in out:
        key = c.chunk_id or c.source_title
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped[:10]


async def _load_reports_context(report_ids: list[str], tenant_id: str) -> str:
    parts: list[str] = []
    for rid in report_ids:
        ctx = await _load_report_context(_uuid(rid), tenant_id)
        if ctx:
            parts.append(ctx)
    return "\n\n".join(parts)


async def _load_report_context(report_id: uuid.UUID, tenant_id: str) -> str:
    async with SessionLocal() as s:
        r = await s.get(Report, report_id)
        if not r or str(r.tenant_id) != tenant_id:
            return ""
        risk_items = (r.content_json or {}).get("risk_items", [])
        risk_str = "\n".join(
            f"- [{ri.get('level','?')}] {ri.get('desc','')}"
            + (f"（{ri.get('law_ref')}）" if ri.get("law_ref") else "")
            for ri in risk_items
            if isinstance(ri, dict)
        )
        return (
            f"【已绑定报告 type={r.type}】\n"
            f"摘要：{r.summary or '（无）'}\n"
            f"风险项：\n{risk_str or '（无）'}"
        )


async def _load_history(session, conv_id: uuid.UUID, turns: int) -> list[Message]:
    res = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(turns * 2)
    )
    rows = list(reversed(res.scalars().all()))
    return rows


def _format_history(rows: list[Message]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in rows:
        role = "assistant" if m.role == "assistant" else "user"
        out.append({"role": role, "content": m.content})
    return out


def _system_prompt(bound_report: bool, *, rag_mode: bool = True) -> str:
    if rag_mode:
        base = "你是枫桥智诉智能助手，帮助用户解答法律相关问题。请依据提供的参考来源回答，标注引用编号如[C1]、[C2]。"
        if bound_report:
            base += "当前会话绑定了用户报告，优先结合报告内容回答。"
        return base
    return "你是枫桥智诉智能助手，帮助用户解答法律相关问题。请用清晰、专业的语言直接回答用户问题。"


def _context_block(citations: list[Citation], report_context: str) -> str:
    parts: list[str] = []
    if report_context:
        parts.append(report_context)
    if citations:
        cit_str = "\n".join(
            f"[C{i+1}] {c.source_title} ({c.source_type})"
            + (f": {c.excerpt}" if c.excerpt else "")
            for i, c in enumerate(citations)
        )
        parts.append(f"参考来源：\n{cit_str}")
    return "\n\n".join(parts) if parts else "（无相关上下文）"


def _extract_meta(answer: str) -> tuple[list[str], int | None, str]:
    import re

    suggested: list[str] = []
    confidence: int | None = None
    body = answer

    sug_match = re.search(r"^建议问题[:：].+$", answer, re.MULTILINE)
    if sug_match:
        raw_qs = sug_match.group(0).split(":", 1)[-1].split("：", 1)[-1].strip()
        suggested = [
            q.strip().lstrip("Qq1234567890.、 ):：")
            for q in re.split(r"[;；]", raw_qs)
            if q.strip()
        ][:3]
        body = answer[: sug_match.start()].strip()

    conf_match = re.search(r"^置信度[:：].+$", body, re.MULTILINE)
    if conf_match:
        try:
            conf_num = re.search(r"\d+", conf_match.group(0))
            if conf_num:
                confidence = max(0, min(100, int(conf_num.group(0))))
        except (ValueError, AttributeError):
            pass
        body = body[: conf_match.start()].strip()

    return suggested, confidence, body


async def _send_error(ws: WebSocket, message: str) -> None:
    await ws.send_json({"type": "error", "message": message})
