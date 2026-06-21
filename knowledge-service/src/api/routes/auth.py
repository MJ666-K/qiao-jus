from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.deps import CurrentUserDep, SessionDep, require_scope
from core.security import create_access_token, create_refresh_token, hash_password, verify_password
from core.tenant import CurrentUser
from models.base import Tenant, User
from schemas.auth import Token, TokenRefresh, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: SessionDep):
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalars().first():
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    tenant = Tenant(name=payload.tenant_name)
    session.add(tenant)
    await session.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        scopes=["read", "write", "admin"],
    )
    session.add(user)
    await session.commit()

    return _issue_tokens(str(user.id), str(tenant.id))


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, session: SessionDep):
    res = await session.execute(select(User).where(User.email == payload.email))
    user = res.scalars().first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return _issue_tokens(str(user.id), str(user.tenant_id))


@router.post("/refresh", response_model=Token)
async def refresh(payload: TokenRefresh):
    from core.security import TokenError, decode_token

    try:
        decoded = decode_token(payload.refresh_token)
    except TokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    if decoded.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not a refresh token")
    return _issue_tokens(decoded["sub"], decoded["tenant_id"])


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUserDep, session: SessionDep):
    res = await session.execute(select(User).where(User.id == _uuid(user.user_id)))
    db_user = res.scalars().first()
    if not db_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user vanished")
    return UserOut(
        id=str(db_user.id),
        tenant_id=str(db_user.tenant_id),
        email=db_user.email,
        scopes=db_user.scopes or [],
    )


def _issue_tokens(user_id: str, tenant_id: str) -> Token:
    return Token(
        access_token=create_access_token(user_id, tenant_id, scopes=["read", "write"]),
        refresh_token=create_refresh_token(user_id, tenant_id),
    )


def _uuid(s: str) -> UUID:
    return UUID(s)
