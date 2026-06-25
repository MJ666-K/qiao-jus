import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from api.deps import CurrentUserDep, SessionDep
from models.base import Assistant, Conversation, Dataset, Message, Report
from schemas.assistant import AssistantCreate, AssistantOut, AssistantSummary, AssistantUpdate

router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.post("", response_model=AssistantOut, status_code=status.HTTP_201_CREATED)
async def create_assistant(payload: AssistantCreate, user: CurrentUserDep, session: SessionDep):
    ds_ids = await _validate_dataset_ids(session, user.tenant_id, payload.dataset_ids)
    rp_ids = await _validate_report_ids(session, user.tenant_id, payload.report_ids)
    assistant = Assistant(
        tenant_id=uuid.UUID(user.tenant_id),
        user_id=uuid.UUID(user.user_id),
        name=payload.name,
        description=payload.description,
        dataset_ids=[str(d) for d in ds_ids],
        report_ids=[str(d) for d in rp_ids],
        enable_thinking=payload.enable_thinking,
    )
    session.add(assistant)
    await session.commit()
    await session.refresh(assistant)
    return _to_out(assistant, 0)


@router.get("", response_model=list[AssistantSummary])
async def list_assistants(user: CurrentUserDep, session: SessionDep, limit: int = 100):
    stmt = (
        select(
            Assistant,
            func.count(Conversation.id).label("conv_count"),
        )
        .outerjoin(Conversation, Conversation.assistant_id == Assistant.id)
        .where(
            Assistant.tenant_id == uuid.UUID(user.tenant_id),
            Assistant.user_id == uuid.UUID(user.user_id),
        )
        .group_by(Assistant.id)
        .order_by(Assistant.updated_at.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    out = []
    for assistant, conv_count in res.all():
        out.append(
            AssistantSummary(
                id=assistant.id,
                name=assistant.name,
                description=assistant.description,
                dataset_ids=_parse_uuid_list(assistant.dataset_ids),
                report_ids=_parse_uuid_list(assistant.report_ids),
                conversation_count=conv_count or 0,
                created_at=assistant.created_at,
                updated_at=assistant.updated_at,
            )
        )
    return out


@router.get("/{assistant_id}", response_model=AssistantOut)
async def get_assistant(assistant_id: str, user: CurrentUserDep, session: SessionDep):
    assistant = await _get_assistant(session, user, assistant_id)
    count = await _conversation_count(session, assistant.id)
    return _to_out(assistant, count)


@router.patch("/{assistant_id}", response_model=AssistantOut)
async def update_assistant(
    assistant_id: str,
    payload: AssistantUpdate,
    user: CurrentUserDep,
    session: SessionDep,
):
    assistant = await _get_assistant(session, user, assistant_id)
    if payload.name is not None:
        assistant.name = payload.name
    if payload.description is not None:
        assistant.description = payload.description
    if payload.enable_thinking is not None:
        assistant.enable_thinking = payload.enable_thinking
    if payload.dataset_ids is not None:
        ds_ids = await _validate_dataset_ids(session, user.tenant_id, payload.dataset_ids)
        assistant.dataset_ids = [str(d) for d in ds_ids]
    if payload.report_ids is not None:
        rp_ids = await _validate_report_ids(session, user.tenant_id, payload.report_ids)
        assistant.report_ids = [str(d) for d in rp_ids]
    await session.commit()
    await session.refresh(assistant)
    count = await _conversation_count(session, assistant.id)
    return _to_out(assistant, count)


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(assistant_id: str, user: CurrentUserDep, session: SessionDep):
    assistant = await _get_assistant(session, user, assistant_id)
    await session.delete(assistant)
    await session.commit()


async def _get_assistant(session, user, assistant_id: str) -> Assistant:
    assistant = await session.get(Assistant, uuid.UUID(assistant_id))
    if (
        not assistant
        or str(assistant.tenant_id) != user.tenant_id
        or str(assistant.user_id) != user.user_id
    ):
        raise HTTPException(404, "assistant not found")
    return assistant


async def _conversation_count(session, assistant_id: uuid.UUID) -> int:
    res = await session.execute(
        select(func.count(Conversation.id)).where(Conversation.assistant_id == assistant_id)
    )
    return res.scalar() or 0


def _to_out(assistant: Assistant, conv_count: int) -> AssistantOut:
    return AssistantOut(
        id=assistant.id,
        tenant_id=assistant.tenant_id,
        user_id=assistant.user_id,
        name=assistant.name,
        description=assistant.description,
        dataset_ids=_parse_uuid_list(assistant.dataset_ids),
        report_ids=_parse_uuid_list(assistant.report_ids),
        enable_thinking=assistant.enable_thinking,
        conversation_count=conv_count,
        created_at=assistant.created_at,
        updated_at=assistant.updated_at,
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


def _parse_uuid_list(raw: list | None) -> list[uuid.UUID]:
    out: list[uuid.UUID] = []
    for item in raw or []:
        try:
            out.append(uuid.UUID(str(item)))
        except (ValueError, TypeError):
            continue
    return out
