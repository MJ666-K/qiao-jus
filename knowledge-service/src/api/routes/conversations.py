import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from api.deps import CurrentUserDep, SessionDep
from api.routes.assistants import _get_assistant
from models.base import Assistant, Conversation, Message, MessageCitation
from schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    ConversationSummary,
    ConversationUpdate,
    MessageOut,
)
from schemas.search import Citation

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, user: CurrentUserDep, session: SessionDep):
    assistant = await _get_assistant(session, user, str(payload.assistant_id))
    enable_thinking = (
        payload.enable_thinking
        if payload.enable_thinking is not None
        else assistant.enable_thinking
    )
    conv = Conversation(
        tenant_id=uuid.UUID(user.tenant_id),
        user_id=uuid.UUID(user.user_id),
        assistant_id=assistant.id,
        title=payload.title,
        enable_thinking=enable_thinking,
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return _to_out(conv, [])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    user: CurrentUserDep,
    session: SessionDep,
    assistant_id: str = Query(...),
    limit: int = 50,
):
    await _get_assistant(session, user, assistant_id)
    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("msg_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(
            Conversation.tenant_id == uuid.UUID(user.tenant_id),
            Conversation.user_id == uuid.UUID(user.user_id),
            Conversation.assistant_id == uuid.UUID(assistant_id),
        )
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    out = []
    for conv, msg_count in res.all():
        out.append(
            ConversationSummary(
                id=conv.id,
                assistant_id=conv.assistant_id,
                title=conv.title,
                message_count=msg_count or 0,
                enable_thinking=conv.enable_thinking,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
    return out


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: str, user: CurrentUserDep, session: SessionDep):
    conv = await _get_conversation(session, user, conversation_id)
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
    payload: ConversationUpdate,
    user: CurrentUserDep,
    session: SessionDep,
):
    conv = await _get_conversation(session, user, conversation_id)
    if payload.title is not None:
        conv.title = payload.title
    if payload.enable_thinking is not None:
        conv.enable_thinking = payload.enable_thinking
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
    conv = await _get_conversation(session, user, conversation_id)
    await session.delete(conv)
    await session.commit()


async def _get_conversation(session, user, conversation_id: str) -> Conversation:
    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if (
        not conv
        or str(conv.tenant_id) != user.tenant_id
        or str(conv.user_id) != user.user_id
    ):
        raise HTTPException(404, "conversation not found")
    return conv


def _to_out(conv: Conversation, messages: list[Message]) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        tenant_id=conv.tenant_id,
        user_id=conv.user_id,
        assistant_id=conv.assistant_id,
        title=conv.title,
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
