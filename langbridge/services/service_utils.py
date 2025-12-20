
"""Utilities for exposing service methods to internal callers."""

from __future__ import annotations

import contextvars
import inspect
from typing import Any, Awaitable, Callable, TypeVar


_INTERNAL_SERVICE_FLAG: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "internal_service_call",
    default=False,
)
_INTERNAL_SERVICE_ATTR = "_internal_service_enabled"

F = TypeVar("F", bound=Callable[..., Any])
R = TypeVar("R")


def internal_service(func: F) -> F:
    """Mark a service method as callable by the internal service user."""

    setattr(func, _INTERNAL_SERVICE_ATTR, True)
    return func


def is_internal_service_call() -> bool:
    """Return True when the current execution context is internal."""

    return _INTERNAL_SERVICE_FLAG.get()


async def call_internal_service(
    func: Callable[..., R] | Callable[..., Awaitable[R]],
    *args: Any,
    **kwargs: Any,
) -> R:
    """Execute a service method as the internal service user.

    Only methods annotated with ``@internal_service`` are callable through this
    helper. The flag is stored in a context variable so nested service calls can
    detect that they should bypass authorization checks.
    """

    if not getattr(func, _INTERNAL_SERVICE_ATTR, False):
        raise ValueError("Target service method is not exposed for internal calls")

    token = _INTERNAL_SERVICE_FLAG.set(True)
    try:
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result
    finally:
        _INTERNAL_SERVICE_FLAG.reset(token)
