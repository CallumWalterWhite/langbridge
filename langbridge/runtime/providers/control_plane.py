from __future__ import annotations

from typing import Any

import httpx

from langbridge.runtime.models import (
    ConnectorMetadata,
    ConnectorSyncState,
    DatasetColumnMetadata,
    DatasetMetadata,
    DatasetPolicyMetadata,
    SemanticModelMetadata,
)
from langbridge.runtime.providers.protocols import (
    ConnectorMetadataProvider,
    DatasetMetadataProvider,
    SemanticModelMetadataProvider,
    SyncStateProvider,
)


class ControlPlaneApiClient:
    def __init__(self, *, base_url: str, service_token: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._timeout = timeout

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["x-langbridge-service-token"] = self._service_token
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(method, f"{self._base_url}{path}", headers=headers, **kwargs)
            response.raise_for_status()
            if not response.content:
                return None
            return response.json()


class ControlPlaneApiDatasetProvider(DatasetMetadataProvider):
    def __init__(self, *, client: ControlPlaneApiClient) -> None:
        self._client = client

    async def get_dataset(self, *, workspace_id, dataset_id) -> DatasetMetadata | None:
        payload = await self._client.request(
            "GET",
            f"/api/v1/runtime-metadata/workspaces/{workspace_id}/datasets/{dataset_id}",
        )
        return DatasetMetadata.model_validate(payload) if payload is not None else None

    async def get_datasets(self, *, workspace_id, dataset_ids) -> list[DatasetMetadata]:
        payload = await self._client.request(
            "POST",
            "/api/v1/runtime-metadata/datasets/batch",
            json={
                "workspace_id": str(workspace_id),
                "dataset_ids": [str(dataset_id) for dataset_id in dataset_ids],
            },
        )
        return [DatasetMetadata.model_validate(item) for item in (payload or [])]

    async def get_dataset_columns(self, *, dataset_id) -> list[DatasetColumnMetadata]:
        payload = await self._client.request(
            "GET",
            f"/api/v1/runtime-metadata/datasets/{dataset_id}/columns",
        )
        return [DatasetColumnMetadata.model_validate(item) for item in (payload or [])]

    async def get_dataset_policy(self, *, dataset_id) -> DatasetPolicyMetadata | None:
        payload = await self._client.request(
            "GET",
            f"/api/v1/runtime-metadata/datasets/{dataset_id}/policy",
        )
        return DatasetPolicyMetadata.model_validate(payload) if payload is not None else None


class ControlPlaneApiConnectorProvider(ConnectorMetadataProvider):
    def __init__(self, *, client: ControlPlaneApiClient) -> None:
        self._client = client

    async def get_connector(self, connector_id) -> ConnectorMetadata | None:
        payload = await self._client.request(
            "GET",
            f"/api/v1/runtime-metadata/connectors/{connector_id}",
        )
        return ConnectorMetadata.model_validate(payload) if payload is not None else None


class ControlPlaneApiSemanticModelProvider(SemanticModelMetadataProvider):
    def __init__(self, *, client: ControlPlaneApiClient) -> None:
        self._client = client

    async def get_semantic_model(self, *, organization_id, semantic_model_id) -> SemanticModelMetadata | None:
        payload = await self._client.request(
            "GET",
            f"/api/v1/runtime-metadata/organizations/{organization_id}/semantic-models/{semantic_model_id}",
        )
        return SemanticModelMetadata.model_validate(payload) if payload is not None else None


class ControlPlaneApiSyncStateProvider(SyncStateProvider):
    def __init__(self, *, client: ControlPlaneApiClient) -> None:
        self._client = client

    async def get_or_create_state(self, **kwargs: Any) -> ConnectorSyncState | None:
        payload = await self._client.request(
            "POST",
            "/api/v1/runtime-metadata/sync-states/upsert",
            json={
                "workspace_id": str(kwargs["workspace_id"]),
                "connection_id": str(kwargs["connection_id"]),
                "connector_type": str(kwargs["connector_type"]),
                "resource_name": str(kwargs["resource_name"]),
                "sync_mode": str(kwargs.get("sync_mode") or "INCREMENTAL"),
            },
        )
        return ConnectorSyncState.model_validate(payload) if payload is not None else None

    async def mark_failed(self, **kwargs: Any) -> None:
        await self._client.request(
            "POST",
            "/api/v1/runtime-metadata/sync-states/fail",
            json={
                "workspace_id": str(kwargs["state"].workspace_id),
                "connection_id": str(kwargs["state"].connection_id),
                "resource_name": str(kwargs["state"].resource_name),
                "error_message": str(kwargs.get("error_message") or ""),
                "status": str(kwargs.get("status") or "failed"),
            },
        )
