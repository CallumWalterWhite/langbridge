from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from langbridge.apps.api.langbridge_api.services.runtime_auth_service import RuntimeAuthService
from langbridge.apps.api.langbridge_api.services.runtime_registry_service import RuntimeRegistryService
from langbridge.packages.common.langbridge_common.contracts.runtime import RuntimeRegistrationRequest
from langbridge.packages.common.langbridge_common.db import agent as _agent  # noqa: F401
from langbridge.packages.common.langbridge_common.db import connector as _connector  # noqa: F401
from langbridge.packages.common.langbridge_common.db import semantic as _semantic  # noqa: F401


@pytest.fixture
def anyio_backend():
    return "asyncio"


@dataclass
class _FakeRuntimeTokenRepo:
    by_hash: dict[str, object]

    def __init__(self) -> None:
        self.by_hash = {}

    async def create_token(
        self,
        *,
        tenant_id,
        token_hash: str,
        expires_at: datetime,
        created_by_user_id,
    ):
        @dataclass
        class _TokenRecord:
            tenant_id: uuid.UUID
            token_hash: str
            expires_at: datetime
            created_by_user_id: uuid.UUID | None
            used_at: datetime | None = None
            runtime_id: uuid.UUID | None = None

        record = _TokenRecord(
            tenant_id=tenant_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
        )
        self.by_hash[token_hash] = record
        return record

    async def get_by_token_hash(self, token_hash: str):
        return self.by_hash.get(token_hash)


@dataclass
class _FakeRuntimeRepo:
    by_id: dict[uuid.UUID, object]

    def __init__(self) -> None:
        self.by_id = {}

    def add(self, runtime) -> object:
        if runtime.id is None:
            runtime.id = uuid.uuid4()
        self.by_id[runtime.id] = runtime
        return runtime

    async def flush(self) -> None:
        return

    async def get_by_id(self, id_: object):
        return self.by_id.get(id_)

    async def get_active_for_tenant(self, tenant_id):
        return [runtime for runtime in self.by_id.values() if runtime.tenant_id == tenant_id]

    async def list_for_tenant(self, tenant_id):
        return [runtime for runtime in self.by_id.values() if runtime.tenant_id == tenant_id]


@pytest.mark.anyio
async def test_runtime_registration_exchanges_token_for_access_token() -> None:
    tenant_id = uuid.uuid4()
    runtime_repo = _FakeRuntimeRepo()
    token_repo = _FakeRuntimeTokenRepo()
    auth_service = RuntimeAuthService()
    service = RuntimeRegistryService(
        runtime_repository=runtime_repo,
        runtime_registration_token_repository=token_repo,
        runtime_auth_service=auth_service,
    )

    raw_token, expires_at = await service.create_registration_token(tenant_id=tenant_id)
    assert expires_at > datetime.now(timezone.utc)

    response = await service.register_runtime(
        RuntimeRegistrationRequest(
            registration_token=raw_token,
            display_name="customer-runtime-1",
            tags=["region:us-east-1"],
            capabilities={"message_types": ["semantic_query_request"]},
        )
    )

    assert response.tenant_id == tenant_id
    assert response.ep_id in runtime_repo.by_id
    assert response.access_token


@pytest.mark.anyio
async def test_runtime_registration_rejects_expired_token() -> None:
    runtime_repo = _FakeRuntimeRepo()
    token_repo = _FakeRuntimeTokenRepo()
    auth_service = RuntimeAuthService()
    service = RuntimeRegistryService(
        runtime_repository=runtime_repo,
        runtime_registration_token_repository=token_repo,
        runtime_auth_service=auth_service,
    )
    expired_token = "expired-token"
    token_hash = auth_service.hash_registration_token(expired_token)
    @dataclass
    class _ExpiredTokenRecord:
        tenant_id: uuid.UUID
        token_hash: str
        expires_at: datetime
        used_at: datetime | None
        runtime_id: uuid.UUID | None = None

    token_repo.by_hash[token_hash] = _ExpiredTokenRecord(
        tenant_id=uuid.uuid4(),
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        used_at=None,
    )

    with pytest.raises(Exception):
        await service.register_runtime(
            RuntimeRegistrationRequest(
                registration_token=expired_token,
                display_name="rt",
            )
        )


@pytest.mark.anyio
async def test_runtime_registry_lists_instances_for_tenant() -> None:
    tenant_id = uuid.uuid4()
    runtime_repo = _FakeRuntimeRepo()
    token_repo = _FakeRuntimeTokenRepo()
    auth_service = RuntimeAuthService()
    service = RuntimeRegistryService(
        runtime_repository=runtime_repo,
        runtime_registration_token_repository=token_repo,
        runtime_auth_service=auth_service,
    )

    raw_token, _ = await service.create_registration_token(tenant_id=tenant_id)
    await service.register_runtime(
        RuntimeRegistrationRequest(
            registration_token=raw_token,
            display_name="runtime-a",
            tags=["semantic_query"],
        )
    )

    runtimes = await service.list_runtimes_for_tenant(tenant_id=tenant_id)
    assert len(runtimes) == 1
    assert runtimes[0].tenant_id == tenant_id
    assert runtimes[0].display_name == "runtime-a"
