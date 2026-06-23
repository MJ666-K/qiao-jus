import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from core.llm import stream_chat
from core.security import TokenError, decode_token
from core.tenant import CurrentUser, set_current_user
from models.base import (
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
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="not access token")
        return

    user_id = payload["sub"]
    tenant_id = payload["tenant_id"]
    set_current_user(CurrentUser(
        user_id=user_id, tenant_id=tenant_id, scopes=tuple(payload.get("scopes") or [])
    ))

    async with SessionLocal() as session:
        user = await session.get(User, _uuid(user_id))
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="user not found")
            return

    await websocket.accept()
    await load_skills()

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
            if mtype == "bind_report":
                if not conversation:
                    await _send_error(websocket, "init required before bind_report")
                    continue
                report_id = msg.get("report_id")
                async with SessionLocal() as s:
                    if report_id:
                        rep = await s.get(Report, _uuid(report_id))
                        if not rep or str(rep.tenant_id) != tenant_id:
                            await _send_error(websocket, "report not found")
                            continue
                        conversation.report_id = rep.id
                    else:
                        conversation.report_id = None
                    s.add(conversation)
                    await s.commit()
                await websocket.send_json({
                    "type": "report_bound",
                    "report_id": str(conversation.report_id) if conversation.report_id else None,
                })
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
                    websocket, conversation, content, tenant_id, stop_event, user_id
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
    report_id = msg.get("report_id")
    async with SessionLocal() as s:
        conv: Conversation | None = None
        if conv_id:
            conv = await s.get(Conversation, _uuid(conv_id))
            if not conv or str(conv.tenant_id) != tenant_id:
                await _send_error(ws, "conversation not found")
                return None
        else:
            r_id = None
            if report_id:
                rep = await s.get(Report, _uuid(report_id))
                if rep and str(rep.tenant_id) == tenant_id:
                    r_id = rep.id
            conv = Conversation(
                tenant_id=_uuid(tenant_id),
                user_id=_uuid(user_id),
                report_id=r_id,
                title="新对话",
            )
            s.add(conv)
            await s.commit()
            await s.refresh(conv)
    await ws.send_json({
        "type": "connected",
        "session_id": str(conv.id),
        "report_id": str(conv.report_id) if conv.report_id else None,
    })
    return conv


async def _handle_message(
    ws: WebSocket,
    conv: Conversation,
    user_content: str,
    tenant_id: str,
    stop_event: asyncio.Event,
    user_id: str | None = None,
) -> None:
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

    citations = await _gather_citations(user_content, tenant_id, conv.report_id, user_id)
    report_context = await _load_report_context(conv.report_id, tenant_id) if conv.report_id else ""

    history_msgs = _format_history(history_rows)
    sys_prompt = _system_prompt(conv.report_id is not None)
    context_block = _context_block(citations, report_context)
    messages = [
        {"role": "system", "content": sys_prompt},
        *history_msgs,
        {"role": "user", "content": f"{user_content}\n\n{context_block}"},
    ]

    streamed_text: list[str] = []
    suggested: list[str] = []
    confidence: int | None = None
    try:
        for chunk in stream_chat(messages, temperature=0.4):
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

    sug_block, conf_block, answer_body = _extract_meta(answer)
    if sug_block:
        suggested = sug_block
    if conf_block is not None:
        confidence = conf_block

    cit_payload = [c.model_dump(mode="json") for c in citations]
    asst_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=answer_body or answer,
        confidence=confidence,
        suggested_questions=suggested,
        citations_json=cit_payload,
    )
    async with SessionLocal() as s:
        s.add(asst_msg)
        await s.flush()
        for c in citations:
            s.add(MessageCitation(
                message_id=asst_msg.id,
                chunk_id=_to_uuid(c.chunk_id) if c.chunk_id else None,
                document_id=_to_uuid(c.document_id) if c.document_id else None,
                source_type=c.source_type,
                source_title=c.source_title,
                excerpt=c.excerpt,
                page=c.page,
            ))
        await s.commit()

    await ws.send_json({
        "type": "done",
        "message_id": str(asst_msg.id),
        "confidence": confidence if confidence is not None else 0,
        "citations": cit_payload,
        "suggested_questions": suggested,
    })


async def _gather_citations(
    query: str, tenant_id: str, report_id: uuid.UUID | None, user_id: str | None = None
) -> list[Citation]:
    out: list[Citation] = []

    if report_id and user_id:
        for dt in ("contract", "dispute"):
            user_hits = await retrieve_children(
                query=query, tenant_id=tenant_id, doc_type=dt, top_k=3, user_id=user_id
            )
            for h in user_hits:
                out.append(Citation(
                    chunk_id=h.get("chunk_id"),
                    document_id=h.get("document_id"),
                    source_type="user_doc",
                    source_title=h.get("source") or "用户材料",
                    excerpt=(h.get("text") or "")[:280],
                    page=h.get("page"),
                    score=h.get("score"),
                ))
        report_hits = await retrieve_children(
            query=query, tenant_id=tenant_id, doc_type="report", top_k=3, user_id=user_id
        )
        for h in report_hits:
            out.append(Citation(
                chunk_id=h.get("chunk_id"),
                document_id=h.get("document_id"),
                source_type="report",
                source_title=h.get("source") or "用户报告",
                excerpt=(h.get("text") or "")[:280],
                page=h.get("page"),
                score=h.get("score"),
            ))

    for doc_type, st in (("law", "law"), ("case", "case")):
        hits = await retrieve_children(
            query=query, tenant_id=tenant_id, doc_type=doc_type, top_k=TOP_K_RETRIEVAL // 2
        )
        for h in hits:
            out.append(Citation(
                chunk_id=h.get("chunk_id"),
                document_id=h.get("document_id"),
                source_type=st,
                source_title=h.get("source") or f"{st}:{h.get('law_name') or ''}".strip(":"),
                excerpt=(h.get("text") or "")[:280],
                page=h.get("page"),
                score=h.get("score"),
            ))

    seen: set[str] = set()
    deduped: list[Citation] = []
    for c in out:
        key = c.chunk_id or c.source_title
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped[:10]


async def _load_report_context(report_id: uuid.UUID | None, tenant_id: str) -> str:
    if not report_id:
        return ""
    async with SessionLocal() as s:
        r = await s.get(Report, report_id)
        if not r or str(r.tenant_id) != tenant_id:
            return ""
        risk_items = (r.content_json or {}).get("risk_items", [])
        risk_str = "\n".join(
            f"- [{ri.get('level','?')}] {ri.get('desc','')}"
            + (f"（{ri.get('law_ref')}）" if ri.get("law_ref") else "")
            for ri in risk_items if isinstance(ri, dict)
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


def _system_prompt(bound_report: bool) -> str:
    base = (
        "你是枫桥智诉智能助手。严格依据上下文作答，标注引用编号 [C1]/[C2] 等；"
        "若上下文不足请明确说明，不要编造。"
    )
    if bound_report:
        base += (
            "\n当前会话绑定了一份用户报告，回答时优先结合报告内容，"
            "引用需区分 [报告]/[用户材料]/[法规]/[类案]。"
        )
    base += (
        "\n回答末尾可附「置信度: NN」与「建议问题: Q1; Q2; Q3」，"
        "其中 NN 为 0-100 整数，Q1-Q3 为后续用户可能追问的简短问题。"
    )
    return base


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

    sug_match = re.search(r"建议问题[:：]\s*(.+)$", answer, re.MULTILINE)
    if sug_match:
        raw_qs = sug_match.group(1).strip()
        suggested = [q.strip().lstrip("Qq1234567890.、 )") for q in re.split(r"[;；]", raw_qs) if q.strip()][:3]
        body = (answer[: sug_match.start()] + answer[sug_match.end():]).strip()

    conf_match = re.search(r"置信度[:：]\s*(\d{1,3})", body)
    if conf_match:
        confidence = max(0, min(100, int(conf_match.group(1))))
        body = (body[: conf_match.start()] + body[conf_match.end():]).strip()

    return suggested, confidence, body


async def _send_error(ws: WebSocket, message: str) -> None:
    await ws.send_json({"type": "error", "message": message})
