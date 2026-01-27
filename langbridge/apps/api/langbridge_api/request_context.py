from __future__ import annotations

import uuid
from dataclasses import dataclass
from contextvars import ContextVar, Token

from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse


@dataclass
class RequestContext:
    user: UserResponse | None = None
    current_org_id: uuid.UUID | None = None
    current_project_id: uuid.UUID | None = None
    correlation_id: str | None = None


_REQUEST_CONTEXT: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def set_request_context(ctx: RequestContext) -> Token:
    return _REQUEST_CONTEXT.set(ctx)


def reset_request_context(token: Token) -> None:
    _REQUEST_CONTEXT.reset(token)


def get_request_context() -> RequestContext:
    ctx = _REQUEST_CONTEXT.get()
    if ctx is None:
        raise RuntimeError("Request context is not set for the current scope.")
    return ctx
