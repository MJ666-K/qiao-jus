import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from api.deps import CurrentUserDep, SessionDep
from models.base import Conversation, Dataset, Message, MessageCitation, Report
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
    rp_ids = list(payload.report_ids)
    if payload.report_id and payload.report_id not in rp_ids:
        rp_ids.insert(0, payload.report_id)
    rp_ids = await _validate_report_ids(session, user.tenant_id, rp_ids)
    ds_ids = await _validate_dataset_ids(session, user.tenant_id, payload.dataset_ids)
    conv = Conversation(
        tenant_id=uuid.UUID(user.tenant_id),
        user_id=uuid.UUID(user.user_id),
        report_id=rp_ids[0] if rp_ids else None,
        report_ids=[str(d) for d in rp_ids],
        title=payload.title,
        track=payload.track,
        enable_thinking=payload.enable_thinking,
        dataset_ids=[str(d) for d in ds_ids],
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
            report_ids=_parse_report_ids(conv),
            dataset_ids=_parse_dataset_ids(conv),
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
    payload: ConversationUpdate,
    user: CurrentUserDep,
    session: SessionDep,
):
    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if not conv or str(conv.tenant_id) != user.tenant_id:
        raise HTTPException(404, "conversation not found")
    if payload.title is not None:
        conv.title = payload.title
    if payload.track is not None:
        conv.track = payload.track
    if payload.enable_thinking is not None:
        conv.enable_thinking = payload.enable_thinking
    if payload.report_ids is not None:
        rp_ids = await _validate_report_ids(session, user.tenant_id, payload.report_ids)
        conv.report_ids = [str(d) for d in rp_ids]
        conv.report_id = rp_ids[0] if rp_ids else None
    elif payload.report_id is not None:
        if payload.report_id:
            r = await session.get(Report, payload.report_id)
            if not r or str(r.tenant_id) != user.tenant_id:
                raise HTTPException(404, "report not found")
            conv.report_id = r.id
            conv.report_ids = [str(r.id)]
        else:
            conv.report_id = None
            conv.report_ids = []
    if payload.dataset_ids is not None:
        ds_ids = await _validate_dataset_ids(session, user.tenant_id, payload.dataset_ids)
        conv.dataset_ids = [str(d) for d in ds_ids]
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
        report_ids=_parse_report_ids(conv),
        dataset_ids=_parse_dataset_ids(conv),
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


async def _validate_dataset_ids(session, tenant_id: str, dataset_ids: list) -> list[uuid.UUID]:
    if not dataset_ids:
        return []
    ids = [uuid.UUID(str(d)) for d in dataset_ids]
    res = await session.execute(
        select(Dataset.id).where(
            Dataset.tenant_id == uuid.UUID(tenant_id),
            Dataset.id.in_(ids),
        )
    )
    found = {row[0] for row in res.all()}
    missing = [d for d in ids if d not in found]
    if missing:
        raise HTTPException(404, f"dataset not found: {missing[0]}")
    return ids


async def _validate_report_ids(session, tenant_id: str, report_ids: list) -> list[uuid.UUID]:
    if not report_ids:
        return []
    ids = [uuid.UUID(str(d)) for d in report_ids]
    res = await session.execute(
        select(Report.id).where(
            Report.tenant_id == uuid.UUID(tenant_id),
            Report.id.in_(ids),
        )
    )
    found = {row[0] for row in res.all()}
    missing = [d for d in ids if d not in found]
    if missing:
        raise HTTPException(404, f"report not found: {missing[0]}")
    return ids


def _parse_report_ids(conv: Conversation) -> list[uuid.UUID]:
    raw = conv.report_ids or []
    out: list[uuid.UUID] = []
    for item in raw:
        try:
            out.append(uuid.UUID(str(item)))
        except (ValueError, TypeError):
            continue
    if not out and conv.report_id:
        out.append(conv.report_id)
    return out


def _parse_dataset_ids(conv: Conversation) -> list[uuid.UUID]:
    raw = conv.dataset_ids or []
    out: list[uuid.UUID] = []
    for item in raw:
        try:
            out.append(uuid.UUID(str(item)))
        except (ValueError, TypeError):
            continue
    return out
