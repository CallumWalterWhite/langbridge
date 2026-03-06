from __future__ import annotations

from langbridge.packages.common.langbridge_common.errors.connector_errors import (
    ConnectorError,
)

from .connector import ApiExtractResult, ApiResource, ApiSyncResult


class StubApiConnectorMixin:
    SUPPORTED_RESOURCES: tuple[str, ...] = ()

    async def test_connection(self) -> None:
        return None

    async def discover_resources(self) -> list[ApiResource]:
        return [
            ApiResource(
                name=resource_name,
                label=resource_name.replace("_", " ").title(),
            )
            for resource_name in self.SUPPORTED_RESOURCES
        ]

    async def extract_resource(
        self,
        resource_name: str,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ApiExtractResult:
        self._ensure_supported_resource(resource_name)
        return ApiExtractResult(
            resource=resource_name,
            status="not_implemented",
            records=[],
            next_cursor=cursor,
            child_records={},
        )

    async def sync_resource(
        self,
        resource_name: str,
        *,
        since: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ApiSyncResult:
        self._ensure_supported_resource(resource_name)
        return ApiSyncResult(
            resource=resource_name,
            status="not_implemented",
            records_synced=0,
            datasets_created=[],
        )

    def _ensure_supported_resource(self, resource_name: str) -> None:
        if resource_name not in self.SUPPORTED_RESOURCES:
            raise ConnectorError(f"Unsupported resource '{resource_name}'.")
