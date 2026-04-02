import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from langbridge.connectors.base.connector import ApiExtractResult, ApiResource
from langbridge.connectors.base.config import ConnectorRuntimeType
from langbridge.runtime.models import DatasetMetadata
from langbridge.runtime.models.metadata import (
    DatasetMaterializationMode,
    DatasetSourceKind,
    DatasetStatus,
    DatasetStorageKind,
    DatasetType,
    LifecycleState,
    ManagementMode,
)
from langbridge.runtime.persistence.db import agent as _db_agent  # noqa: F401
from langbridge.runtime.persistence.db import semantic as _db_semantic  # noqa: F401
from langbridge.runtime.persistence.db.connector_sync import ConnectorSyncStateRecord
from langbridge.runtime.persistence.db.dataset import (
    DatasetColumnRecord,
    DatasetPolicyRecord,
    DatasetRecord,
    DatasetRevisionRecord,
)
from langbridge.runtime.persistence.db.lineage import LineageEdgeRecord
from langbridge.runtime.services.dataset_sync_service import ConnectorSyncRuntime
from langbridge.runtime.settings import runtime_settings


SYNC_MODE_INCREMENTAL = "INCREMENTAL"
SYNC_MODE_FULL_REFRESH = "FULL_REFRESH"
SYNC_STATUS_SUCCEEDED = "succeeded"
SYNC_STATUS_FAILED = "failed"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def dataset_storage_dir(tmp_path: Path):
    original_dataset_dir = runtime_settings.DATASET_FILE_LOCAL_DIR
    object.__setattr__(
        runtime_settings,
        "DATASET_FILE_LOCAL_DIR",
        str((tmp_path / "datasets").resolve()),
    )
    try:
        yield tmp_path / "datasets"
    finally:
        object.__setattr__(runtime_settings, "DATASET_FILE_LOCAL_DIR", original_dataset_dir)


@dataclass
class _FakeConnectorRecord:
    name: str


class _FakeConnectorSyncStateRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[uuid.UUID, uuid.UUID, str], ConnectorSyncStateRecord] = {}

    def add(self, state: ConnectorSyncStateRecord) -> None:
        self.items[(state.workspace_id, state.connection_id, state.resource_name)] = state

    async def save(self, state: ConnectorSyncStateRecord) -> ConnectorSyncStateRecord:
        self.add(state)
        return state

    async def get_for_resource(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        resource_name: str,
    ) -> ConnectorSyncStateRecord | None:
        return self.items.get((workspace_id, connection_id, resource_name))

    async def list_for_connection(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> list[ConnectorSyncStateRecord]:
        return [
            state
            for (row_workspace_id, row_connection_id, _), state in self.items.items()
            if row_workspace_id == workspace_id and row_connection_id == connection_id
        ]


class _FakeDatasetRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, DatasetRecord] = {}

    def add(self, dataset: DatasetRecord) -> None:
        self.items[dataset.id] = dataset

    async def save(self, dataset: DatasetRecord) -> DatasetRecord:
        self.add(dataset)
        return dataset

    async def find_file_dataset_for_connection(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        table_name: str,
    ) -> DatasetRecord | None:
        for dataset in self.items.values():
            if (
                dataset.workspace_id == workspace_id
                and dataset.connection_id == connection_id
                and dataset.dataset_type == "FILE"
                and str(dataset.materialization_mode or "").strip().lower() == "synced"
                and dataset.table_name == table_name
            ):
                return dataset
        return None

    async def list_for_connection(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        dataset_types: list[str] | None = None,
        limit: int = 500,
    ) -> list[DatasetRecord]:
        rows = [
            dataset
            for dataset in self.items.values()
            if dataset.workspace_id == workspace_id and dataset.connection_id == connection_id
        ]
        if dataset_types:
            allowed = {item.upper() for item in dataset_types}
            rows = [dataset for dataset in rows if dataset.dataset_type.upper() in allowed]
        rows.sort(key=lambda dataset: dataset.updated_at, reverse=True)
        return rows[:limit]


class _FakeDatasetColumnRepository:
    def __init__(self) -> None:
        self.by_dataset: dict[uuid.UUID, list[DatasetColumnRecord]] = {}

    def add(self, column: DatasetColumnRecord) -> None:
        self.by_dataset.setdefault(column.dataset_id, []).append(column)

    async def list_for_dataset(self, *, dataset_id: uuid.UUID) -> list[DatasetColumnRecord]:
        rows = list(self.by_dataset.get(dataset_id, []))
        rows.sort(key=lambda item: (item.ordinal_position, item.name))
        return rows

    async def delete_for_dataset(self, *, dataset_id: uuid.UUID) -> None:
        self.by_dataset[dataset_id] = []


class _FakeDatasetPolicyRepository:
    def __init__(self) -> None:
        self.by_dataset: dict[uuid.UUID, DatasetPolicyRecord] = {}

    def add(self, policy: DatasetPolicyRecord) -> None:
        self.by_dataset[policy.dataset_id] = policy

    async def save(self, policy: DatasetPolicyRecord) -> DatasetPolicyRecord:
        self.add(policy)
        return policy

    async def get_for_dataset(self, *, dataset_id: uuid.UUID) -> DatasetPolicyRecord | None:
        return self.by_dataset.get(dataset_id)


class _FakeDatasetRevisionRepository:
    def __init__(self) -> None:
        self.by_dataset: dict[uuid.UUID, list[DatasetRevisionRecord]] = {}

    def add(self, revision: DatasetRevisionRecord) -> None:
        self.by_dataset.setdefault(revision.dataset_id, []).append(revision)

    async def next_revision_number(self, *, dataset_id: uuid.UUID) -> int:
        rows = self.by_dataset.get(dataset_id) or []
        if not rows:
            return 1
        return max(row.revision_number for row in rows) + 1


class _FakeLineageEdgeRepository:
    def __init__(self) -> None:
        self.items: list[LineageEdgeRecord] = []

    def add(self, edge: LineageEdgeRecord) -> None:
        self.items.append(edge)

    async def delete_for_target(
        self,
        *,
        workspace_id: uuid.UUID,
        target_type: str,
        target_id: str,
    ) -> None:
        self.items = [
            edge
            for edge in self.items
            if not (
                edge.workspace_id == workspace_id
                and edge.target_type == target_type
                and edge.target_id == target_id
            )
        ]


class _QueueConnector:
    def __init__(self, *responses: ApiExtractResult | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def extract_resource(
        self,
        resource_name: str,
        *,
        since: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ApiExtractResult:
        self.calls.append(
            {
                "resource_name": resource_name,
                "since": since,
                "cursor": cursor,
                "limit": limit,
            }
        )
        if not self._responses:
            raise AssertionError("No queued API response available.")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _build_runtime() -> tuple[
    ConnectorSyncRuntime,
    _FakeConnectorSyncStateRepository,
    _FakeDatasetRepository,
    _FakeDatasetRevisionRepository,
    _FakeLineageEdgeRepository,
]:
    state_repository = _FakeConnectorSyncStateRepository()
    dataset_repository = _FakeDatasetRepository()
    dataset_column_repository = _FakeDatasetColumnRepository()
    dataset_policy_repository = _FakeDatasetPolicyRepository()
    dataset_revision_repository = _FakeDatasetRevisionRepository()
    lineage_edge_repository = _FakeLineageEdgeRepository()
    runtime = ConnectorSyncRuntime(
        connector_sync_state_repository=state_repository,
        dataset_repository=dataset_repository,
        dataset_column_repository=dataset_column_repository,
        dataset_policy_repository=dataset_policy_repository,
        dataset_revision_repository=dataset_revision_repository,
        lineage_edge_repository=lineage_edge_repository,
    )
    return (
        runtime,
        state_repository,
        dataset_repository,
        dataset_revision_repository,
        lineage_edge_repository,
    )


def _resource(
    *,
    name: str = "orders",
    primary_key: str | None = "id",
    supports_incremental: bool = True,
    incremental_cursor_field: str | None = "updated_at",
) -> ApiResource:
    return ApiResource(
        name=name,
        label=name.title(),
        path=name,
        primary_key=primary_key,
        cursor_field="page_info" if supports_incremental else None,
        incremental_cursor_field=incremental_cursor_field,
        supports_incremental=supports_incremental,
        default_sync_mode="INCREMENTAL" if supports_incremental else "FULL_REFRESH",
    )


def _declared_synced_dataset(
    *,
    workspace_id: uuid.UUID,
    actor_id: uuid.UUID,
    connection_id: uuid.UUID,
    connector_type: ConnectorRuntimeType,
    name: str,
    resource: str,
    flatten: list[str] | None = None,
) -> DatasetMetadata:
    now = datetime.now(timezone.utc)
    sync_config: dict[str, Any] = {
        "resource": resource,
        "strategy": SYNC_MODE_INCREMENTAL,
    }
    if flatten:
        sync_config["flatten"] = list(flatten)
    return DatasetMetadata(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        connection_id=connection_id,
        created_by=actor_id,
        updated_by=actor_id,
        name=name,
        sql_alias=name,
        description=f"Declared synced dataset for resource path '{resource}'.",
        tags=[],
        dataset_type=DatasetType.FILE,
        materialization_mode=DatasetMaterializationMode.SYNCED,
        source_kind=DatasetSourceKind.API,
        connector_kind=connector_type.value.lower(),
        storage_kind=DatasetStorageKind.PARQUET,
        dialect="duckdb",
        catalog_name=None,
        schema_name=None,
        table_name=name,
        storage_uri=None,
        sql_text=None,
        source=None,
        sync=sync_config,
        relation_identity=None,
        execution_capabilities=None,
        referenced_dataset_ids=[],
        federated_plan=None,
        file_config={
            "format": "parquet",
            "managed_dataset": True,
        },
        status=DatasetStatus.PENDING_SYNC,
        revision_id=None,
        row_count_estimate=None,
        bytes_estimate=None,
        last_profiled_at=None,
        columns=[],
        policy=None,
        created_at=now,
        updated_at=now,
        management_mode=ManagementMode.CONFIG_MANAGED,
        lifecycle_state=LifecycleState.ACTIVE,
    )


def _parquet_rows(
    runtime: ConnectorSyncRuntime,
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    dataset_name: str,
) -> list[dict[str, Any]]:
    path = runtime._dataset_parquet_path(
        workspace_id=workspace_id,
        connection_id=connection_id,
        dataset_name=dataset_name,
    )
    table = pq.read_table(path)
    return table.to_pylist()


@pytest.mark.anyio
async def test_connector_sync_runtime_flattens_only_explicit_one_to_one_children(
    dataset_storage_dir: Path,
) -> None:
    runtime, _, dataset_repository, dataset_revision_repository, lineage_edge_repository = _build_runtime()

    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    dataset = _declared_synced_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        name="shopify_orders",
        resource="orders",
        flatten=["customer"],
    )
    dataset_repository.add(dataset)
    state = await runtime.get_or_create_state(
        workspace_id=workspace_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        resource_name="orders",
        sync_mode=SYNC_MODE_INCREMENTAL,
    )
    connector = _QueueConnector(
        ApiExtractResult(
            resource="orders",
            records=[
                {
                    "id": 101,
                    "updated_at": "2026-03-01T00:00:00Z",
                    "total_price": "42.00",
                    "customer": {
                        "id": "cust_101",
                        "email": "ada@example.com",
                    },
                    "line_items": [
                        {"id": 9001, "title": "Hat"},
                    ],
                }
            ],
            checkpoint_cursor="2026-03-01T00:00:00Z",
        )
    )

    summary = await runtime.sync_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_record=_FakeConnectorRecord(name="Shopify storefront"),
        connector_type=ConnectorRuntimeType.SHOPIFY,
        dataset=dataset,
        resource=_resource(),
        api_connector=connector,
        state=state,
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    assert summary["resource_name"] == "orders"
    assert summary["records_synced"] == 1
    assert summary["dataset_names"] == ["shopify_orders"]
    assert state.status == SYNC_STATUS_SUCCEEDED
    assert state.last_cursor == "2026-03-01T00:00:00Z"
    assert len(dataset_repository.items) == 1

    rows = _parquet_rows(
        runtime,
        workspace_id=workspace_id,
        connection_id=connection_id,
        dataset_name=dataset.name,
    )
    assert rows == [
        {
            "customer__email": "ada@example.com",
            "customer__id": "cust_101",
            "id": 101,
            "total_price": "42.00",
            "updated_at": "2026-03-01T00:00:00Z",
        }
    ]
    assert "line_items" not in rows[0]
    assert len(dataset_revision_repository.by_dataset[dataset.id]) == 1
    assert any(edge.source_type == "api_resource" for edge in lineage_edge_repository.items)
    assert any(edge.source_type == "file_resource" for edge in lineage_edge_repository.items)
    assert {child["path"] for child in state.state["child_resources"]} >= {
        "orders.customer",
        "orders.line_items",
    }


@pytest.mark.anyio
async def test_connector_sync_runtime_materializes_explicit_child_resource_path_dataset(
    dataset_storage_dir: Path,
) -> None:
    runtime, _, dataset_repository, _, _ = _build_runtime()

    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    dataset = _declared_synced_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        name="shopify_order_line_items",
        resource="orders.line_items",
    )
    dataset_repository.add(dataset)
    state = await runtime.get_or_create_state(
        workspace_id=workspace_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        resource_name="orders.line_items",
        sync_mode=SYNC_MODE_INCREMENTAL,
    )
    connector = _QueueConnector(
        ApiExtractResult(
            resource="orders",
            records=[
                {
                    "id": 101,
                    "updated_at": "2026-03-01T00:00:00Z",
                    "line_items": [
                        {"id": 9001, "title": "Hat"},
                        {"id": 9002, "title": "Scarf"},
                    ],
                }
            ],
            checkpoint_cursor="2026-03-01T00:00:00Z",
        )
    )

    summary = await runtime.sync_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_record=_FakeConnectorRecord(name="Shopify storefront"),
        connector_type=ConnectorRuntimeType.SHOPIFY,
        dataset=dataset,
        resource=_resource(),
        api_connector=connector,
        state=state,
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    assert summary["resource_name"] == "orders.line_items"
    assert summary["root_resource_name"] == "orders"
    assert summary["records_synced"] == 2
    assert summary["dataset_names"] == ["shopify_order_line_items"]
    assert len(dataset_repository.items) == 1

    rows = _parquet_rows(
        runtime,
        workspace_id=workspace_id,
        connection_id=connection_id,
        dataset_name=dataset.name,
    )
    assert rows == [
        {"_child_index": 0, "_parent_id": 101, "id": 9001, "title": "Hat"},
        {"_child_index": 1, "_parent_id": 101, "id": 9002, "title": "Scarf"},
    ]


@pytest.mark.anyio
async def test_connector_sync_runtime_rejects_flattening_one_to_many_child_path(
    dataset_storage_dir: Path,
) -> None:
    runtime, _, dataset_repository, _, _ = _build_runtime()

    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    dataset = _declared_synced_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        name="shopify_orders",
        resource="orders",
        flatten=["line_items"],
    )
    dataset_repository.add(dataset)
    state = await runtime.get_or_create_state(
        workspace_id=workspace_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        resource_name="orders",
        sync_mode=SYNC_MODE_INCREMENTAL,
    )
    connector = _QueueConnector(
        ApiExtractResult(
            resource="orders",
            records=[
                {
                    "id": 101,
                    "updated_at": "2026-03-01T00:00:00Z",
                    "line_items": [{"id": 9001, "title": "Hat"}],
                }
            ],
            checkpoint_cursor="2026-03-01T00:00:00Z",
        )
    )

    with pytest.raises(ValueError, match="cannot flatten a one-to-many child"):
        await runtime.sync_dataset(
            workspace_id=workspace_id,
            actor_id=actor_id,
            connection_id=connection_id,
            connector_record=_FakeConnectorRecord(name="Shopify storefront"),
            connector_type=ConnectorRuntimeType.SHOPIFY,
            dataset=dataset,
            resource=_resource(),
            api_connector=connector,
            state=state,
            sync_mode=SYNC_MODE_INCREMENTAL,
        )

    assert dataset_repository.items[dataset.id].storage_uri is None


@pytest.mark.anyio
async def test_connector_sync_runtime_incremental_second_sync_only_upserts_new_records(
    dataset_storage_dir: Path,
) -> None:
    runtime, _, dataset_repository, _, _ = _build_runtime()

    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    dataset = _declared_synced_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        name="shopify_orders",
        resource="orders",
    )
    dataset_repository.add(dataset)
    state = await runtime.get_or_create_state(
        workspace_id=workspace_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        resource_name="orders",
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    first_connector = _QueueConnector(
        ApiExtractResult(
            resource="orders",
            records=[
                {"id": 1, "updated_at": "2026-03-01T00:00:00Z", "total_price": "10.00"},
                {"id": 2, "updated_at": "2026-03-01T00:30:00Z", "total_price": "20.00"},
            ],
            checkpoint_cursor="2026-03-01T00:30:00Z",
        )
    )
    await runtime.sync_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_record=_FakeConnectorRecord(name="Shopify"),
        connector_type=ConnectorRuntimeType.SHOPIFY,
        dataset=dataset,
        resource=_resource(),
        api_connector=first_connector,
        state=state,
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    second_connector = _QueueConnector(
        ApiExtractResult(
            resource="orders",
            records=[
                {"id": 2, "updated_at": "2026-03-02T00:00:00Z", "total_price": "25.00"},
                {"id": 3, "updated_at": "2026-03-02T01:00:00Z", "total_price": "30.00"},
            ],
            checkpoint_cursor="2026-03-02T01:00:00Z",
        )
    )
    await runtime.sync_dataset(
        workspace_id=workspace_id,
        actor_id=uuid.uuid4(),
        connection_id=connection_id,
        connector_record=_FakeConnectorRecord(name="Shopify"),
        connector_type=ConnectorRuntimeType.SHOPIFY,
        dataset=dataset_repository.items[dataset.id],
        resource=_resource(),
        api_connector=second_connector,
        state=state,
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    assert second_connector.calls[0]["since"] == "2026-03-01T00:30:00Z"
    assert state.last_cursor == "2026-03-02T01:00:00Z"

    rows = _parquet_rows(
        runtime,
        workspace_id=workspace_id,
        connection_id=connection_id,
        dataset_name=dataset.name,
    )
    assert len(rows) == 3
    by_id = {row["id"]: row for row in rows}
    assert by_id[2]["total_price"] == "25.00"
    assert by_id[3]["updated_at"] == "2026-03-02T01:00:00Z"


@pytest.mark.anyio
async def test_connector_sync_runtime_falls_back_to_full_refresh_for_non_incremental_resources(
    dataset_storage_dir: Path,
) -> None:
    runtime, _, dataset_repository, _, _ = _build_runtime()

    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    dataset = _declared_synced_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.GOOGLE_ANALYTICS,
        name="ga_sessions",
        resource="sessions",
    )
    dataset_repository.add(dataset)
    state = await runtime.get_or_create_state(
        workspace_id=workspace_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.GOOGLE_ANALYTICS,
        resource_name="sessions",
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    first_connector = _QueueConnector(
        ApiExtractResult(
            resource="sessions",
            records=[{"id": "a", "sessions": 12}, {"id": "b", "sessions": 6}],
        )
    )
    await runtime.sync_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_record=_FakeConnectorRecord(name="Analytics"),
        connector_type=ConnectorRuntimeType.GOOGLE_ANALYTICS,
        dataset=dataset,
        resource=_resource(
            name="sessions",
            incremental_cursor_field=None,
            supports_incremental=False,
        ),
        api_connector=first_connector,
        state=state,
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    second_connector = _QueueConnector(
        ApiExtractResult(
            resource="sessions",
            records=[{"id": "c", "sessions": 99}],
        )
    )
    await runtime.sync_dataset(
        workspace_id=workspace_id,
        actor_id=uuid.uuid4(),
        connection_id=connection_id,
        connector_record=_FakeConnectorRecord(name="Analytics"),
        connector_type=ConnectorRuntimeType.GOOGLE_ANALYTICS,
        dataset=dataset_repository.items[dataset.id],
        resource=_resource(
            name="sessions",
            incremental_cursor_field=None,
            supports_incremental=False,
        ),
        api_connector=second_connector,
        state=state,
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    rows = _parquet_rows(
        runtime,
        workspace_id=workspace_id,
        connection_id=connection_id,
        dataset_name=dataset.name,
    )
    assert rows == [{"id": "c", "sessions": 99}]
    assert state.sync_mode == SYNC_MODE_FULL_REFRESH
    assert first_connector.calls[0]["since"] is None
    assert second_connector.calls[0]["since"] is None


@pytest.mark.anyio
async def test_connector_sync_runtime_failure_does_not_advance_checkpoint_state(
    dataset_storage_dir: Path,
) -> None:
    runtime, _, dataset_repository, _, _ = _build_runtime()

    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    dataset = _declared_synced_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        name="shopify_orders",
        resource="orders",
    )
    dataset_repository.add(dataset)
    state = await runtime.get_or_create_state(
        workspace_id=workspace_id,
        connection_id=connection_id,
        connector_type=ConnectorRuntimeType.SHOPIFY,
        resource_name="orders",
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    successful_connector = _QueueConnector(
        ApiExtractResult(
            resource="orders",
            records=[{"id": 1, "updated_at": "2026-03-01T00:00:00Z"}],
            checkpoint_cursor="2026-03-01T00:00:00Z",
        )
    )
    await runtime.sync_dataset(
        workspace_id=workspace_id,
        actor_id=actor_id,
        connection_id=connection_id,
        connector_record=_FakeConnectorRecord(name="Shopify"),
        connector_type=ConnectorRuntimeType.SHOPIFY,
        dataset=dataset,
        resource=_resource(),
        api_connector=successful_connector,
        state=state,
        sync_mode=SYNC_MODE_INCREMENTAL,
    )

    failed_connector = _QueueConnector(RuntimeError("upstream timeout"))
    with pytest.raises(RuntimeError):
        await runtime.sync_dataset(
            workspace_id=workspace_id,
            actor_id=uuid.uuid4(),
            connection_id=connection_id,
            connector_record=_FakeConnectorRecord(name="Shopify"),
            connector_type=ConnectorRuntimeType.SHOPIFY,
            dataset=dataset_repository.items[dataset.id],
            resource=_resource(),
            api_connector=failed_connector,
            state=state,
            sync_mode=SYNC_MODE_INCREMENTAL,
        )
    await runtime.mark_failed(state=state, error_message="upstream timeout")

    assert state.last_cursor == "2026-03-01T00:00:00Z"
    assert state.status == SYNC_STATUS_FAILED
    assert state.error_message == "upstream timeout"
