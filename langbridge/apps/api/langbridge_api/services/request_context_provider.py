from __future__ import annotations

import uuid

from langbridge.apps.api.langbridge_api.request_context import RequestContext
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse


class RequestContextProvider:
    """Thin wrapper to expose request-scoped context data."""

    def __init__(self, request_context: RequestContext) -> None:
        self._context = request_context

    @property
    def user(self) -> UserResponse | None:
        return self._context.user

    @property
    def current_org_id(self) -> uuid.UUID | None:
        return self._context.current_org_id

    @property
    def current_project_id(self) -> uuid.UUID | None:
        return self._context.current_project_id

    @property
    def correlation_id(self) -> str | None:
        return self._context.correlation_id

    @property
    def has_outbox_message(self) -> bool:
        return self._context.has_outbox_message

    def mark_outbox_message(self) -> None:
        self._context.has_outbox_message = True
