from contextvars import ContextVar, Token
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

_session_ctx: ContextVar[Optional[AsyncSession]] = ContextVar("db_session", default=None)


def set_session(session: AsyncSession) -> Token:
    return _session_ctx.set(session)


def reset_session(token: Token) -> None:
    _session_ctx.reset(token)


def get_session() -> AsyncSession:
    session = _session_ctx.get()
    if session is None:
        raise RuntimeError("Database session is not set for the current context.")
    return session
