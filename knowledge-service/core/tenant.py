from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    tenant_id: str
    scopes: tuple[str, ...] = ()


_current_user: ContextVar[CurrentUser | None] = ContextVar("current_user", default=None)


def set_current_user(user: CurrentUser) -> None:
    _current_user.set(user)


def get_current_user() -> CurrentUser | None:
    return _current_user.get()
