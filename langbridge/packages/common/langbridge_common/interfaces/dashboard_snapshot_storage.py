from typing import Any, Protocol
from uuid import UUID


class IDashboardSnapshotReader(Protocol):
    async def read_snapshot(
        self,
        *,
        organization_id: UUID,
        dashboard_id: UUID,
        snapshot_reference: str,
    ) -> dict[str, Any] | None: ...


class IDashboardSnapshotWriter(Protocol):
    async def write_snapshot(
        self,
        *,
        organization_id: UUID,
        dashboard_id: UUID,
        data: dict[str, Any],
    ) -> str: ...


class IDashboardSnapshotDeleter(Protocol):
    async def delete_snapshot(
        self,
        *,
        organization_id: UUID,
        dashboard_id: UUID,
        snapshot_reference: str,
    ) -> None: ...


class IDashboardSnapshotStorage(
    IDashboardSnapshotReader,
    IDashboardSnapshotWriter,
    IDashboardSnapshotDeleter,
    Protocol,
):
    """Composite protocol for dashboard snapshot backends."""
