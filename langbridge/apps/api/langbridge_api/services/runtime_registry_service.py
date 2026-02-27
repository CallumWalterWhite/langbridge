from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from langbridge.apps.api.langbridge_api.services.runtime_auth_service import RuntimeAuthService
from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.common.langbridge_common.contracts.runtime import (
    RuntimeCapabilitiesUpdateRequest,
    RuntimeCapabilitiesUpdateResponse,
    RuntimeHeartbeatRequest,
    RuntimeHeartbeatResponse,
    RuntimeInstanceResponse,
    RuntimeRegistrationRequest,
    RuntimeRegistrationResponse,
)
from langbridge.packages.common.langbridge_common.db.runtime import (
    RuntimeInstanceRecord,
    RuntimeInstanceStatus,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.common.langbridge_common.repositories.runtime_repository import (
    RuntimeInstanceRepository,
    RuntimeRegistrationTokenRepository,
)


class RuntimeRegistryService:
    def __init__(
        self,
        runtime_repository: RuntimeInstanceRepository,
        runtime_registration_token_repository: RuntimeRegistrationTokenRepository,
        runtime_auth_service: RuntimeAuthService,
    ) -> None:
        self._runtime_repository = runtime_repository
        self._runtime_registration_token_repository = runtime_registration_token_repository
        self._runtime_auth_service = runtime_auth_service

    async def create_registration_token(
        self,
        *,
        tenant_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None = None,
    ) -> tuple[str, datetime]:
        raw_token = self._runtime_auth_service.create_registration_token()
        token_hash = self._runtime_auth_service.hash_registration_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=max(1, int(settings.EDGE_RUNTIME_REGISTRATION_TOKEN_TTL_MINUTES))
        )
        await self._runtime_registration_token_repository.create_token(
            tenant_id=tenant_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
        )
        return raw_token, expires_at

    async def register_runtime(
        self,
        request: RuntimeRegistrationRequest,
    ) -> RuntimeRegistrationResponse:
        token_hash = self._runtime_auth_service.hash_registration_token(request.registration_token)
        registration_token = await self._runtime_registration_token_repository.get_by_token_hash(
            token_hash
        )
        if registration_token is None:
            raise BusinessValidationError("Registration token is invalid.")

        now = datetime.now(timezone.utc)
        if registration_token.used_at is not None:
            raise BusinessValidationError("Registration token has already been used.")
        if registration_token.expires_at <= now:
            raise BusinessValidationError("Registration token has expired.")

        runtime = RuntimeInstanceRecord(
            tenant_id=registration_token.tenant_id,
            display_name=request.display_name,
            tags=request.tags,
            capabilities=request.capabilities,
            metadata_json=request.metadata,
            status=RuntimeInstanceStatus.active,
            last_seen_at=now,
            registered_at=now,
            created_at=now,
            updated_at=now,
        )
        self._runtime_repository.add(runtime)
        await self._runtime_repository.flush()

        registration_token.runtime_id = runtime.id
        registration_token.used_at = now

        access_token, expires_at = self._runtime_auth_service.issue_runtime_access_token(
            tenant_id=registration_token.tenant_id,
            ep_id=runtime.id,
        )
        return RuntimeRegistrationResponse(
            ep_id=runtime.id,
            tenant_id=registration_token.tenant_id,
            access_token=access_token,
            expires_at=expires_at,
        )

    async def heartbeat(
        self,
        *,
        tenant_id: uuid.UUID,
        ep_id: uuid.UUID,
        request: RuntimeHeartbeatRequest,
    ) -> RuntimeHeartbeatResponse:
        runtime = await self._runtime_repository.get_by_id(ep_id)
        if runtime is None or runtime.tenant_id != tenant_id:
            raise BusinessValidationError("Runtime instance is not registered for this tenant.")

        runtime.last_seen_at = datetime.now(timezone.utc)
        if request.status in {status.value for status in RuntimeInstanceStatus}:
            runtime.status = RuntimeInstanceStatus(request.status)
        if request.metadata:
            metadata = dict(runtime.metadata_json or {})
            metadata.update(request.metadata)
            runtime.metadata_json = metadata

        access_token, expires_at = self._runtime_auth_service.issue_runtime_access_token(
            tenant_id=tenant_id,
            ep_id=ep_id,
        )
        return RuntimeHeartbeatResponse(
            server_time=datetime.now(timezone.utc),
            access_token=access_token,
            expires_at=expires_at,
        )

    async def update_capabilities(
        self,
        *,
        tenant_id: uuid.UUID,
        ep_id: uuid.UUID,
        request: RuntimeCapabilitiesUpdateRequest,
    ) -> RuntimeCapabilitiesUpdateResponse:
        runtime = await self._runtime_repository.get_by_id(ep_id)
        if runtime is None or runtime.tenant_id != tenant_id:
            raise BusinessValidationError("Runtime instance is not registered for this tenant.")

        runtime.tags = request.tags
        runtime.capabilities = request.capabilities
        runtime.last_seen_at = datetime.now(timezone.utc)
        return RuntimeCapabilitiesUpdateResponse(updated_at=datetime.now(timezone.utc))

    async def select_runtime_for_dispatch(
        self,
        *,
        tenant_id: uuid.UUID,
        message_type: str,
        required_tags: list[str] | None = None,
    ) -> RuntimeInstanceRecord:
        runtimes = await self._runtime_repository.get_active_for_tenant(tenant_id)
        if not runtimes:
            raise BusinessValidationError("No active customer runtime is available for this tenant.")

        required_tag_set = set(required_tags or [])
        for runtime in runtimes:
            runtime_tags = set(runtime.tags or [])
            if not required_tag_set.issubset(runtime_tags):
                continue
            capability_types = set((runtime.capabilities or {}).get("message_types", []))
            if capability_types and message_type not in capability_types:
                continue
            return runtime
        raise BusinessValidationError(
            "No runtime matched required tags/capabilities for this task."
        )

    async def get_runtime_for_token(self, *, tenant_id: uuid.UUID, ep_id: uuid.UUID) -> RuntimeInstanceRecord:
        runtime = await self._runtime_repository.get_by_id(ep_id)
        if runtime is None or runtime.tenant_id != tenant_id:
            raise BusinessValidationError("Runtime instance is not registered for this tenant.")
        return runtime

    async def list_runtimes_for_tenant(self, *, tenant_id: uuid.UUID) -> list[RuntimeInstanceResponse]:
        runtimes = await self._runtime_repository.list_for_tenant(tenant_id)
        return [
            RuntimeInstanceResponse(
                ep_id=runtime.id,
                tenant_id=runtime.tenant_id,
                display_name=runtime.display_name,
                status=runtime.status.value,
                tags=list(runtime.tags or []),
                capabilities=dict(runtime.capabilities or {}),
                metadata=dict(runtime.metadata_json or {}),
                registered_at=runtime.registered_at,
                last_seen_at=runtime.last_seen_at,
                updated_at=runtime.updated_at,
            )
            for runtime in runtimes
        ]
