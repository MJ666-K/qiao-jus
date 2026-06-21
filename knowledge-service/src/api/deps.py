from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import TokenError, decode_token
from core.tenant import CurrentUser, set_current_user
from models.base import User
from storage.postgres import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except TokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}") from e

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")

    user_id = payload["sub"]
    user = await session.get(User, _to_uuid(user_id))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")

    current = CurrentUser(
        user_id=user_id,
        tenant_id=payload["tenant_id"],
        scopes=tuple(user.scopes or []),
    )
    set_current_user(current)
    return current


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_scope(scope: str):
    async def checker(user: CurrentUserDep) -> CurrentUser:
        if scope != "read" and scope not in user.scopes and "admin" not in user.scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"missing scope: {scope}")
        return user
    return checker


def _to_uuid(s: str):
    import uuid

    return uuid.UUID(s)
