from uuid import UUID
import asyncio

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.deps import CurrentUserDep, SessionDep, require_scope
from core.captcha import create_captcha, verify_captcha
from core.security import create_access_token, create_refresh_token, hash_password, verify_password
from core.tenant import CurrentUser
from models.base import Tenant, User
from schemas.auth import CaptchaResponse, Token, TokenRefresh, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/captcha", response_model=CaptchaResponse)
async def captcha():
    key, image = await asyncio.to_thread(create_captcha)
    return CaptchaResponse(captcha_key=key, image=image)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: SessionDep):
    if not verify_captcha(payload.captcha_key, payload.captcha_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalars().first():
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已被注册")

    tenant = Tenant(name=payload.tenant_name)
    session.add(tenant)
    await session.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
        display_name=payload.display_name,
        scopes=["read", "write"],
    )
    session.add(user)
    await session.commit()

    return _issue_tokens(str(user.id), str(tenant.id), "user")


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, session: SessionDep):
    if not verify_captcha(payload.captcha_key, payload.captcha_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")
    res = await session.execute(select(User).where(User.email == payload.email))
    user = res.scalars().first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    return _issue_tokens(str(user.id), str(user.tenant_id), user.role)


@router.post("/refresh", response_model=Token)
async def refresh(payload: TokenRefresh, session: SessionDep):
    from core.security import TokenError, decode_token

    try:
        decoded = decode_token(payload.refresh_token)
    except TokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录凭证无效或已过期") from e
    if decoded.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌类型错误")
    user_id = decoded["sub"]
    res = await session.execute(select(User).where(User.id == UUID(user_id)))
    db_user = res.scalars().first()
    if not db_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return _issue_tokens(decoded["sub"], decoded["tenant_id"], db_user.role)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUserDep, session: SessionDep):
    res = await session.execute(select(User).where(User.id == _uuid(user.user_id)))
    db_user = res.scalars().first()
    if not db_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return UserOut(
        id=str(db_user.id),
        tenant_id=str(db_user.tenant_id),
        email=db_user.email,
        role=db_user.role,
        display_name=db_user.display_name,
        scopes=db_user.scopes or [],
    )


def _issue_tokens(user_id: str, tenant_id: str, role: str = "user") -> Token:
    return Token(
        access_token=create_access_token(user_id, tenant_id, scopes=["read", "write"], role=role),
        refresh_token=create_refresh_token(user_id, tenant_id, role),
    )


def _uuid(s: str) -> UUID:
    return UUID(s)
