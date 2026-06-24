import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from api.deps import CurrentUserDep, SessionDep
from models.base import Conversation, Message, MessageCitation, Report
from schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    ConversationSummary,
    MessageOut,
)
from schemas.search import Citation

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, user: CurrentUserDep, session: SessionDep):
    report_id = None
    if payload.report_id:
        r = await session.get(Report, payload.report_id)
        if not r or str(r.tenant_id) != user.tenant_id:
            raise HTTPException(404, "report not found")
        report_id = r.id
    conv = Conversation(
        tenant_id=uuid.UUID(user.tenant_id),
        user_id=uuid.UUID(user.user_id),
        report_id=report_id,
        title=payload.title,
        track=payload.track,
        enable_thinking=payload.enable_thinking,
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return _to_out(conv, [])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(user: CurrentUserDep, session: SessionDep, limit: int = 50):
    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("msg_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.tenant_id == uuid.UUID(user.tenant_id))
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    out = []
    for conv, msg_count in res.all():
        out.append(ConversationSummary(
            id=conv.id,
            title=conv.title,
            report_id=conv.report_id,
            track=conv.track,
            message_count=msg_count or 0,
            enable_thinking=conv.enable_thinking,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        ))
    return out


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: str, user: CurrentUserDep, session: SessionDep):
    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if not conv or str(conv.tenant_id) != user.tenant_id:
        raise HTTPException(404, "conversation not found")
    res = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = res.scalars().all()
    return _to_out(conv, messages)


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: str,
    payload: ConversationCreate,
    user: CurrentUserDep,
    session: SessionDep,
):
    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if not conv or str(conv.tenant_id) != user.tenant_id:
        raise HTTPException(404, "conversation not found")
    if payload.title:
        conv.title = payload.title
    if payload.track:
        conv.track = payload.track
    # enable_thinking can be explicitly set to False, so check for None
    if payload.enable_thinking is not None:
        conv.enable_thinking = payload.enable_thinking
    if payload.report_id:
        r = await session.get(Report, payload.report_id)
        if not r or str(r.tenant_id) != user.tenant_id:
            raise HTTPException(404, "report not found")
        conv.report_id = r.id
    await session.commit()
    await session.refresh(conv)
    res = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = res.scalars().all()
    return _to_out(conv, messages)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str, user: CurrentUserDep, session: SessionDep):
    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if not conv or str(conv.tenant_id) != user.tenant_id:
        raise HTTPException(404, "conversation not found")
    await session.delete(conv)
    await session.commit()


def _to_out(conv: Conversation, messages: list[Message]) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        tenant_id=conv.tenant_id,
        user_id=conv.user_id,
        report_id=conv.report_id,
        title=conv.title,
        track=conv.track,
        enable_thinking=conv.enable_thinking,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[_msg_out(m) for m in messages],
    )


def _msg_out(m: Message) -> MessageOut:
    cits = [c for c in (m.citations_json or []) if isinstance(c, dict)]
    return MessageOut(
        id=m.id,
        role=m.role,
        content=m.content,
        confidence=m.confidence,
        suggested_questions=m.suggested_questions or [],
        citations=[Citation(**c) for c in cits],
        created_at=m.created_at,
    )
