from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from langbridge.packages.common.langbridge_common.config import settings


class LocalDashboardSnapshotStorage:
    """Filesystem-backed snapshot storage for dashboard result payloads."""

    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir).resolve()

    async def read_snapshot(
        self,
        *,
        organization_id: UUID,
        dashboard_id: UUID,
        snapshot_reference: str,
    ) -> dict[str, Any] | None:
        path = self._resolve_reference(snapshot_reference)
        if not path.exists():
            return None
        try:
            content = path.read_text(encoding="utf-8")
            payload = json.loads(content)
            if not isinstance(payload, dict):
                return None
            return payload
        except (OSError, json.JSONDecodeError):
            return None

    async def write_snapshot(
        self,
        *,
        organization_id: UUID,
        dashboard_id: UUID,
        data: dict[str, Any],
    ) -> str:
        reference = self._build_reference(organization_id=organization_id, dashboard_id=dashboard_id)
        path = self._resolve_reference(reference)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
        return reference

    async def delete_snapshot(
        self,
        *,
        organization_id: UUID,
        dashboard_id: UUID,
        snapshot_reference: str,
    ) -> None:
        path = self._resolve_reference(snapshot_reference)
        if not path.exists():
            return
        try:
            path.unlink()
        except OSError:
            return

    def _build_reference(self, *, organization_id: UUID, dashboard_id: UUID) -> str:
        return f"{organization_id}/{dashboard_id}.json"

    def _resolve_reference(self, reference: str) -> Path:
        # Prevent directory traversal by resolving under the configured base dir.
        candidate = (self._base_dir / reference).resolve()
        if self._base_dir not in candidate.parents and candidate != self._base_dir:
            raise ValueError("Invalid snapshot reference.")
        return candidate


def create_dashboard_snapshot_storage() -> LocalDashboardSnapshotStorage:
    backend = settings.DASHBOARD_SNAPSHOT_STORAGE_BACKEND
    if backend == "local":
        return LocalDashboardSnapshotStorage(settings.DASHBOARD_SNAPSHOT_LOCAL_DIR)
    if backend in {"azure_blob", "s3"}:
        raise NotImplementedError(
            f"Dashboard snapshot storage backend '{backend}' is not implemented yet."
        )
    raise ValueError(f"Unsupported dashboard snapshot storage backend: {backend}")
