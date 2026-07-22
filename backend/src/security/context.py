from contextlib import contextmanager
from contextvars import ContextVar


_CURRENT_USER_ID: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def current_user_id() -> str | None:
    return _CURRENT_USER_ID.get()


@contextmanager
def bind_user(user_id: str):
    token = _CURRENT_USER_ID.set(user_id)
    try:
        yield
    finally:
        _CURRENT_USER_ID.reset(token)
