from __future__ import annotations

import uuid

from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.common.langbridge_common.contracts.runtime import ExecutionMode
from .environment_service import EnvironmentService


class ExecutionRoutingService:
    EXECUTION_MODE_KEY = "execution_mode"

    def __init__(self, environment_service: EnvironmentService) -> None:
        self._environment_service = environment_service

    async def get_mode_for_tenant(self, tenant_id: uuid.UUID) -> ExecutionMode:
        try:
            raw_mode = await self._environment_service.get_setting(
                organization_id=tenant_id,
                key=self.EXECUTION_MODE_KEY,
                default=settings.DEFAULT_EXECUTION_MODE,
            )
        except Exception:
            raw_mode = settings.DEFAULT_EXECUTION_MODE
        try:
            return ExecutionMode(str(raw_mode).strip().lower())
        except ValueError:
            return ExecutionMode.hosted
