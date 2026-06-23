import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from api.deps import CurrentUserDep, SessionDep, require_admin
from models.base import User
from schemas.auth import UserOut, UserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    user: CurrentUserDep,
    session: SessionDep,
):
    if user.role != "admin":
        raise HTTPException(403, "admin role required")
    res = await session.execute(
        select(User).where(User.tenant_id == uuid.UUID(user.tenant_id))
    )
    return [
        UserOut(
            id=str(u.id),
            tenant_id=str(u.tenant_id),
            email=u.email,
            role=u.role,
            display_name=u.display_name,
            scopes=u.scopes or [],
        )
        for u in res.scalars().all()
    ]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    user: CurrentUserDep,
    session: SessionDep,
):
    if user.role != "admin":
        raise HTTPException(403, "admin role required")
    u = await session.get(User, uuid.UUID(user_id))
    if not u:
        raise HTTPException(404, "user not found")
    if payload.role is not None:
        if payload.role not in ("user", "admin"):
            raise HTTPException(400, "role must be 'user' or 'admin'")
        u.role = payload.role
    if payload.display_name is not None:
        u.display_name = payload.display_name
    await session.commit()
    await session.refresh(u)
    return UserOut(
        id=str(u.id),
        tenant_id=str(u.tenant_id),
        email=u.email,
        role=u.role,
        display_name=u.display_name,
        scopes=u.scopes or [],
    )
