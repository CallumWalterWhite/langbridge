from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from langbridge.packages.runtime.models.base import RuntimeModel


class ConnectorSyncState(RuntimeModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    connector_type: str
    resource_name: str
    sync_mode: str = "INCREMENTAL"
    last_cursor: str | None = None
    last_sync_at: datetime | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    status: str = "never_synced"
    error_message: str | None = None
    records_synced: int = 0
    bytes_synced: int | None = None
    dataset_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def state_json(self) -> dict[str, Any]:
        return dict(self.state)


class SqlJobResultArtifact(RuntimeModel):
    id: uuid.UUID
    sql_job_id: uuid.UUID
    workspace_id: uuid.UUID
    created_by: uuid.UUID
    format: str
    mime_type: str
    row_count: int = 0
    byte_size: int | None = None
    storage_backend: str
    storage_reference: str
    payload: dict[str, Any] | None = None
    created_at: datetime | None = None

    @property
    def payload_json(self) -> dict[str, Any] | None:
        return None if self.payload is None else dict(self.payload)
