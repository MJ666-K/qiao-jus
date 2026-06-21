from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from core.config import settings

ALGORITHM = settings.jwt_algorithm


def hash_password(plain: str) -> str:
    # bcrypt has a 72-byte limit; passlib+bcrypt 4.x has a known bug in its
    # wrap-bug detection that breaks on modern bcrypt. Call bcrypt directly.
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def _create_token(sub: str, tenant_id: str, scopes: list[str], ttl: timedelta, kind: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": sub,
        "tenant_id": tenant_id,
        "scopes": scopes,
        "type": kind,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: str, tenant_id: str, scopes: list[str] | None = None) -> str:
    return _create_token(
        user_id,
        tenant_id,
        scopes or [],
        timedelta(minutes=settings.jwt_access_ttl_minutes),
        "access",
    )


def create_refresh_token(user_id: str, tenant_id: str) -> str:
    return _create_token(
        user_id,
        tenant_id,
        [],
        timedelta(days=settings.jwt_refresh_ttl_days),
        "refresh",
    )


class TokenError(Exception):
    pass


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise TokenError(str(e)) from e
