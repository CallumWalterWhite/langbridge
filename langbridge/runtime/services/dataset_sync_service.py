import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Mapping

import pyarrow as pa
import pyarrow.parquet as pq

from langbridge.connectors.base.connector import ApiConnector
from langbridge.connectors.base.resource_paths import (
    api_resource_root,
    materialize_api_resource_rows,
    normalize_api_resource_path,
)
from langbridge.connectors.base import (
    ApiConnectorFactory,
    SqlConnectorFactory,
    get_connector_config_factory,
)
from langbridge.runtime.utils.lineage import (
    LineageEdgeType,
    LineageNodeType,
    build_api_resource_id,
    build_file_resource_id,
    build_source_table_resource_id,
    stable_payload_hash,
)
from langbridge.runtime.utils.connector_runtime import build_connector_runtime_payload
from langbridge.runtime.utils.datasets import (
    build_dataset_execution_capabilities,
    build_dataset_relation_identity,
)
from langbridge.connectors.base.connector import ApiResource
from langbridge.connectors.base.config import ConnectorRuntimeType, ConnectorSyncStrategy
from langbridge.runtime.models import (
    ConnectorSyncState,
    DatasetColumnMetadata,
    DatasetMaterializationMode,
    DatasetMetadata,
    DatasetPolicyMetadata,
    DatasetStatus,
    DatasetType,
    DatasetRevision,
    DatasetSyncConfig,
    LineageEdge,
)
from langbridge.runtime.ports import (
    ConnectorSyncStateStore,
    DatasetCatalogStore,
    DatasetColumnStore,
    DatasetPolicyStore,
    DatasetRevisionStore,
    LineageEdgeStore,
)
from langbridge.runtime.models.metadata import (
    ConnectorMetadata,
    DatasetSourceKind,
    DatasetSource,
    DatasetStorageKind,
)
from langbridge.runtime.models.state import ConnectorSyncMode, ConnectorSyncStatus
from langbridge.runtime.security import SecretProviderRegistry
from langbridge.runtime.settings import runtime_settings as settings

_RESOURCE_SANITIZER = re.compile(r"[^0-9A-Za-z_]+")


async def _flush_stores(*stores: Any) -> None:
    for store in stores:
        flush = getattr(store, "flush", None)
        if callable(flush):
            await flush()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _relation_parts(relation_name: str) -> tuple[str | None, str | None, str]:
    parts = [part.strip() for part in str(relation_name or "").split(".") if part.strip()]
    if not parts:
        raise ValueError("Dataset table source must not be empty.")
    if len(parts) == 1:
        return None, None, parts[0]
    if len(parts) == 2:
        return None, parts[0], parts[1]
    return parts[0], parts[1], parts[2]


@dataclass(slots=True)
class MaterializedDatasetResult:
    dataset_id: uuid.UUID
    dataset_name: str
    source_key: str
    row_count: int
    bytes_written: int | None
    schema_drift: dict[str, Any] | None = None


class ConnectorSyncRuntime:
    def __init__(
        self,
        *,
        connector_sync_state_repository: ConnectorSyncStateStore,
        dataset_repository: DatasetCatalogStore,
        dataset_column_repository: DatasetColumnStore,
        dataset_policy_repository: DatasetPolicyStore,
        dataset_revision_repository: DatasetRevisionStore | None = None,
        lineage_edge_repository: LineageEdgeStore | None = None,
        secret_provider_registry: SecretProviderRegistry | None = None,
    ) -> None:
        self._connector_sync_state_repository = connector_sync_state_repository
        self._dataset_repository = dataset_repository
        self._dataset_column_repository = dataset_column_repository
        self._dataset_policy_repository = dataset_policy_repository
        self._dataset_revision_repository = dataset_revision_repository
        self._lineage_edge_repository = lineage_edge_repository
        self._secret_provider_registry = secret_provider_registry or SecretProviderRegistry()
        self._api_connector_factory = ApiConnectorFactory()
        self._sql_connector_factory = SqlConnectorFactory()

    async def get_or_create_state(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        connector_type: ConnectorRuntimeType,
        resource_name: str,
        sync_mode: Any,
    ) -> ConnectorSyncState:
        sync_mode_value = ConnectorSyncMode(_enum_value(sync_mode).upper())
        state = await self._connector_sync_state_repository.get_for_resource(
            workspace_id=workspace_id,
            connection_id=connection_id,
            resource_name=resource_name,
        )
        if state is not None:
            return state
        state = ConnectorSyncState(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            connection_id=connection_id,
            connector_type=connector_type,
            source_key=resource_name,
            source={},
            sync_mode=sync_mode_value,
            last_cursor=None,
            last_sync_at=None,
            state={},
            status=ConnectorSyncStatus.NEVER_SYNCED,
            error_message=None,
            records_synced=0,
            bytes_synced=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._connector_sync_state_repository.add(state)
        return state

    @staticmethod
    def _sync_source(dataset: DatasetMetadata) -> DatasetSource:
        sync_meta = dict(dataset.sync_json or {})
        source = sync_meta.get("source")
        if not isinstance(source, dict) or not source:
            raise ValueError(f"Dataset '{dataset.name}' is missing sync.source.")
        return DatasetSource.model_validate(source)

    @staticmethod
    def _sync_source_key(source: DatasetSource) -> str:
        if source.resource:
            return f"resource:{str(source.resource).strip()}"
        if source.table:
            return f"table:{str(source.table).strip()}"
        if source.sql:
            return f"sql:{stable_payload_hash(str(source.sql).strip())}"
        if source.storage_uri:
            return f"storage:{str(source.storage_uri).strip()}"
        raise ValueError("Dataset sync source is missing.")

    @staticmethod
    def _sync_source_kind(source: DatasetSource) -> DatasetSourceKind:
        if source.resource:
            return DatasetSourceKind.API
        if source.table or source.sql:
            return DatasetSourceKind.DATABASE
        if source.storage_uri:
            return DatasetSourceKind.FILE
        raise ValueError("Dataset sync source is missing.")

    @staticmethod
    def _sync_source_payload(source: DatasetSource) -> dict[str, Any]:
        return source.model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _sync_source_label(source: DatasetSource) -> str:
        if source.resource:
            return f"resource path '{str(source.resource).strip()}'"
        if source.table:
            return f"table '{str(source.table).strip()}'"
        if source.sql:
            return "SQL query"
        if source.storage_uri:
            return f"storage source '{str(source.storage_uri).strip()}'"
        return "sync source"

    def _build_api_connector(self, connector_record: ConnectorMetadata) -> ApiConnector:
        if connector_record.connector_type is None:
            raise ValueError(f"Connector '{connector_record.name}' is missing connector_type.")
        runtime_payload = build_connector_runtime_payload(
            config_json=connector_record.config,
            connection_metadata=(
                connector_record.connection_metadata.model_dump(mode="json", by_alias=True)
                if connector_record.connection_metadata is not None
                else None
            ),
            secret_references={
                key: value.model_dump(mode="json")
                for key, value in (connector_record.secret_references or {}).items()
            },
            secret_resolver=self._secret_provider_registry.resolve,
        )
        config_factory = get_connector_config_factory(connector_record.connector_type)
        return self._api_connector_factory.create_api_connector(
            connector_record.connector_type,
            config_factory.create(runtime_payload.get("config") or {}),
            logger=logging.getLogger("langbridge.runtime.sync.dataset"),
        )

    def _build_sql_connector(self, connector_record: ConnectorMetadata):
        if connector_record.connector_type is None:
            raise ValueError(f"Connector '{connector_record.name}' is missing connector_type.")
        runtime_payload = build_connector_runtime_payload(
            config_json=connector_record.config,
            connection_metadata=(
                connector_record.connection_metadata.model_dump(mode="json", by_alias=True)
                if connector_record.connection_metadata is not None
                else None
            ),
            secret_references={
                key: value.model_dump(mode="json")
                for key, value in (connector_record.secret_references or {}).items()
            },
            secret_resolver=self._secret_provider_registry.resolve,
        )
        config_factory = get_connector_config_factory(connector_record.connector_type)
        return self._sql_connector_factory.create_sql_connector(
            connector_record.connector_type,
            config_factory.create(runtime_payload.get("config") or {}),
            logger=logging.getLogger("langbridge.runtime.sync.dataset"),
        )

    async def _resolve_api_root_resource(
        self,
        *,
        dataset: DatasetMetadata,
        connector: ConnectorMetadata,
        api_connector: ApiConnector,
        resource_name: str,
    ) -> ApiResource:
        discovered_resources = {
            resource.name: resource for resource in await api_connector.discover_resources()
        }
        resource = discovered_resources.get(resource_name)
        if resource is not None:
            return resource

        resolver = getattr(api_connector, "resolve_resource", None)
        if callable(resolver):
            resolved_resource = resolver(resource_name)
            if hasattr(resolved_resource, "__await__"):
                resolved_resource = await resolved_resource
            if isinstance(resolved_resource, ApiResource):
                return resolved_resource

        raise ValueError(
            f"Dataset '{dataset.name}' is bound to connector '{connector.name}', "
            f"but connector resource '{resource_name}' was not found."
        )

    async def sync_dataset(
        self,
        *,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        connector_record: ConnectorMetadata,
        dataset: DatasetMetadata,
        sync_mode: ConnectorSyncMode,
        max_sync_retry: int = 3,
    ) -> dict[str, Any]:
        if connector_record.connector_type is None:
            raise ValueError(f"Connector '{connector_record.name}' is missing connector_type.")

        connection_id = connector_record.id
        connector_type = connector_record.connector_type
        normalized_sync_mode = ConnectorSyncMode(_enum_value(sync_mode).upper())
        sync_source = self._sync_source(dataset)
        source_payload = self._sync_source_payload(sync_source)
        source_key = self._sync_source_key(sync_source)
        state = await self.get_or_create_state(
            workspace_id=workspace_id,
            connection_id=connection_id,
            connector_type=connector_type,
            resource_name=source_key,
            sync_mode=normalized_sync_mode,
        )
        state.status = ConnectorSyncStatus.RUNNING
        state.sync_mode = normalized_sync_mode
        state.error_message = None
        state.updated_at = datetime.now(timezone.utc)
        state.source_key = source_key
        state.source_kind = self._sync_source_kind(sync_source)
        state.source = source_payload
        await self._connector_sync_state_repository.save(state)

        if sync_source.resource:
            api_connector = self._build_api_connector(connector_record)
            await api_connector.test_connection()
            resource_path = normalize_api_resource_path(str(sync_source.resource).strip())
            resolved_resource = await self._resolve_api_root_resource(
                dataset=dataset,
                connector=connector_record,
                api_connector=api_connector,
                resource_name=api_resource_root(resource_path),
            )
            effective_sync_mode = normalized_sync_mode
            if normalized_sync_mode == ConnectorSyncMode.INCREMENTAL and not resolved_resource.supports_incremental:
                effective_sync_mode = ConnectorSyncMode.FULL_REFRESH

            since = None
            if effective_sync_mode == ConnectorSyncMode.INCREMENTAL and resolved_resource.supports_incremental:
                since = state.last_cursor

            page_cursor: str | None = None
            page_count = 0
            extracted_records: list[dict[str, Any]] = []
            checkpoint_cursor = state.last_cursor
            for _ in range(max_sync_retry):
                extract_result = await api_connector.extract_resource(
                    resolved_resource.name,
                    since=since,
                    cursor=page_cursor,
                    limit=None,
                )
                extracted_records.extend(list(extract_result.records or []))
                checkpoint_cursor = self._pick_newer_cursor(
                    checkpoint_cursor, extract_result.checkpoint_cursor
                )
                page_count += 1
                page_cursor = extract_result.next_cursor
                if not page_cursor:
                    break

            now = datetime.now(timezone.utc)
            materialized_rows = materialize_api_resource_rows(
                resource_path=resource_path,
                records=extracted_records,
                primary_key=resolved_resource.primary_key,
                flatten=source_payload.get("flatten"),
            )
            materialized = await self._materialize_existing_dataset(
                actor_id=actor_id,
                connection_id=connection_id,
                connector_record=connector_record,
                connector_type=connector_type,
                dataset=dataset,
                sync_source=sync_source,
                source_key=source_key,
                rows=materialized_rows.rows,
                primary_key=self._materialization_primary_key(
                    resource_path=resource_path,
                    root_resource_name=resolved_resource.name,
                    root_primary_key=resolved_resource.primary_key,
                    rows=materialized_rows.rows,
                ),
                sync_mode=effective_sync_mode,
            )

            state.sync_mode = effective_sync_mode
            state.last_cursor = (
                checkpoint_cursor
                if effective_sync_mode == ConnectorSyncMode.INCREMENTAL
                and resolved_resource.supports_incremental
                else state.last_cursor
            )
            state.last_sync_at = now
            state.status = ConnectorSyncStatus.SUCCEEDED
            state.error_message = None
            state.records_synced = len(materialized_rows.rows)
            state.bytes_synced = materialized.bytes_written
            state.state = {
                "page_count": page_count,
                "resource_path": resource_path,
                "root_resource_name": resolved_resource.name,
                "dataset_id": str(materialized.dataset_id),
                "dataset_name": materialized.dataset_name,
                "cardinality": materialized_rows.cardinality.value,
                "schema_drift": materialized.schema_drift,
                "child_resources": [
                    {
                        "name": child.name,
                        "path": child.path,
                        "parent_path": child.parent_path,
                        "cardinality": child.cardinality.value,
                        "supports_flattening": child.supports_flattening,
                        "addressable": child.addressable,
                    }
                    for child in materialized_rows.child_resources
                ],
                "last_sync_at": now.isoformat(),
            }
            state.updated_at = now
            await self._connector_sync_state_repository.save(state)
            return {
                "source_key": source_key,
                "source": source_payload,
                "resource_name": resource_path,
                "root_resource_name": resolved_resource.name,
                "sync_mode": _enum_value(effective_sync_mode),
                "records_synced": int(state.records_synced or 0),
                "bytes_synced": materialized.bytes_written,
                "last_cursor": state.last_cursor,
                "dataset_ids": [str(materialized.dataset_id)],
                "dataset_names": [materialized.dataset_name],
            }

        if sync_source.table or sync_source.sql:
            sql_connector = self._build_sql_connector(connector_record)
            await sql_connector.test_connection()
            source_query = (
                f"SELECT * FROM {str(sync_source.table).strip()}"
                if sync_source.table
                else str(sync_source.sql).strip()
            )
            effective_sync_mode = normalized_sync_mode
            if (
                normalized_sync_mode == ConnectorSyncMode.INCREMENTAL
                and state.last_cursor is not None
                and str(dataset.sync.cursor_field or "").strip()
            ):
                cursor_field = str(dataset.sync.cursor_field or "").strip()
                cursor_literal = self._sql_literal(state.last_cursor)
                wrapped = f"SELECT * FROM ({source_query}) AS langbridge_sync_source"
                source_query = f"{wrapped} WHERE {cursor_field} >= {cursor_literal}"
            result = await sql_connector.execute(
                source_query,
                params={},
                max_rows=None,
                timeout_s=30,
            )
            rows = [
                {
                    str(column): (raw_row[index] if index < len(raw_row) else None)
                    for index, column in enumerate(result.columns)
                }
                for raw_row in result.rows
            ]
            primary_key = await self._resolve_sql_primary_key(
                sql_connector=sql_connector,
                sync_source=sync_source,
                rows=rows,
            )
            materialized = await self._materialize_existing_dataset(
                actor_id=actor_id,
                connection_id=connection_id,
                connector_record=connector_record,
                connector_type=connector_type,
                dataset=dataset,
                sync_source=sync_source,
                source_key=source_key,
                rows=rows,
                primary_key=primary_key,
                sync_mode=effective_sync_mode,
            )
            now = datetime.now(timezone.utc)
            state.sync_mode = effective_sync_mode
            state.last_cursor = self._resolve_next_sql_cursor(
                rows=rows,
                cursor_field=str(dataset.sync.cursor_field or "").strip() or None,
                current_cursor=state.last_cursor,
                sync_mode=effective_sync_mode,
            )
            state.last_sync_at = now
            state.status = ConnectorSyncStatus.SUCCEEDED
            state.error_message = None
            state.records_synced = len(rows)
            state.bytes_synced = materialized.bytes_written
            state.state = {
                "query_sql": result.sql,
                "row_count": len(rows),
                "source_label": self._sync_source_label(sync_source),
                "schema_drift": materialized.schema_drift,
                "dataset_id": str(materialized.dataset_id),
                "dataset_name": materialized.dataset_name,
                "last_sync_at": now.isoformat(),
            }
            state.updated_at = now
            await self._connector_sync_state_repository.save(state)
            return {
                "source_key": source_key,
                "source": source_payload,
                "sync_mode": _enum_value(effective_sync_mode),
                "records_synced": int(state.records_synced or 0),
                "bytes_synced": materialized.bytes_written,
                "last_cursor": state.last_cursor,
                "dataset_ids": [str(materialized.dataset_id)],
                "dataset_names": [materialized.dataset_name],
            }

        raise ValueError(
            f"Dataset '{dataset.name}' uses unsupported sync.source shape. "
            "Supported synced sources are resource, table, and sql."
        )

    async def mark_failed(self, *, state: ConnectorSyncState, error_message: str) -> None:
        state.status = ConnectorSyncStatus.FAILED
        state.error_message = error_message
        state.updated_at = datetime.now(timezone.utc)
        await self._connector_sync_state_repository.save(state)

    async def _materialize_existing_dataset(
        self,
        *,
        actor_id: uuid.UUID,
        connection_id: uuid.UUID,
        connector_record: ConnectorMetadata,
        connector_type: ConnectorRuntimeType,
        dataset: DatasetMetadata,
        sync_source: DatasetSource,
        source_key: str,
        rows: list[dict[str, Any]],
        primary_key: str | None,
        sync_mode: ConnectorSyncMode,
    ) -> MaterializedDatasetResult:
        normalized_sync_mode = ConnectorSyncMode(_enum_value(sync_mode).upper())
        parquet_path = self._dataset_parquet_path(
            workspace_id=dataset.workspace_id,
            connection_id=connection_id,
            dataset_name=dataset.name,
        )
        existing_rows, existing_schema = self._read_existing_rows(parquet_path)
        merged_rows = self._merge_rows(
            existing_rows=existing_rows,
            new_rows=rows,
            primary_key=primary_key,
            full_refresh=normalized_sync_mode == ConnectorSyncMode.FULL_REFRESH,
        )
        table = self._rows_to_table(rows=merged_rows, existing_schema=existing_schema)
        schema_drift = self._describe_schema_drift(existing_schema=existing_schema, next_schema=table.schema)
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, parquet_path)
        storage_uri = parquet_path.resolve().as_uri()
        bytes_written = parquet_path.stat().st_size if parquet_path.exists() else None
        now = datetime.now(timezone.utc)

        file_config = {
            "format": "parquet",
            "managed_dataset": True,
        }

        existing_sync = dataset.sync
        if existing_sync is None:
            raise ValueError(f"Dataset '{dataset.name}' is missing a sync contract.")
        previously_materialized = bool(str(dataset.storage_uri or "").strip())
        dataset.connection_id = connection_id
        dataset.updated_by = actor_id
        if not str(dataset.description or "").strip():
            dataset.description = self._dataset_description(
                connector_record.name,
                self._sync_source_label(sync_source),
            )
        dataset.tags = self._merge_tags(
            existing=list(dataset.tags_json or []),
            required=self._dataset_tags(connector_type=connector_type, source=sync_source),
        )
        dataset.dataset_type = DatasetType.FILE
        dataset.materialization_mode = DatasetMaterializationMode.SYNCED
        dataset.source = None
        dataset.sync = DatasetSyncConfig(
            source=self._sync_source_payload(sync_source),
            strategy=existing_sync.strategy or ConnectorSyncStrategy(_enum_value(normalized_sync_mode)),
            cadence=existing_sync.cadence,
            sync_on_start=bool(existing_sync.sync_on_start),
            cursor_field=existing_sync.cursor_field,
            initial_cursor=existing_sync.initial_cursor,
            lookback_window=existing_sync.lookback_window,
            backfill_start=existing_sync.backfill_start,
            backfill_end=existing_sync.backfill_end,
        )
        dataset.source_kind = self._sync_source_kind(sync_source)
        dataset.connector_kind = connector_type.value.lower()
        dataset.storage_kind = DatasetStorageKind.PARQUET
        dataset.dialect = "duckdb"
        dataset.schema_name = None
        dataset.table_name = dataset.table_name or self._dataset_sql_alias(dataset.name)
        dataset.storage_uri = storage_uri
        dataset.file_config = file_config
        dataset.status = DatasetStatus.PUBLISHED
        dataset.row_count_estimate = len(merged_rows)
        dataset.bytes_estimate = bytes_written
        dataset.updated_at = now
        self._apply_dataset_descriptor_metadata(dataset=dataset)
        if not previously_materialized:
            change_summary = (
                f"Initial sync materialized dataset '{dataset.name}' from "
                f"{self._sync_source_label(sync_source)}."
            )
        else:
            change_summary = (
                f"{_enum_value(normalized_sync_mode).replace('_', ' ').title()} sync updated dataset "
                f"'{dataset.name}' from {self._sync_source_label(sync_source)}."
            )

        await self._replace_columns(dataset=dataset, table=table)
        policy = await self._get_or_create_policy(dataset=dataset)
        await self._create_dataset_revision(
            dataset=dataset,
            policy=policy,
            created_by=actor_id,
            change_summary=change_summary,
        )
        await self._replace_dataset_lineage(dataset=dataset)
        await self._dataset_repository.save(dataset)

        return MaterializedDatasetResult(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            source_key=source_key,
            row_count=len(merged_rows),
            bytes_written=bytes_written,
            schema_drift=schema_drift,
        )

    async def _replace_columns(self, *, dataset: DatasetMetadata, table: pa.Table) -> None:
        await self._dataset_column_repository.delete_for_dataset(dataset_id=dataset.id)
        # Persist deletes before re-inserting the refreshed schema so
        # predeclared synced datasets do not trip the unique
        # (dataset_id, name) constraint in the metadata store.
        await _flush_stores(self._dataset_column_repository)
        now = datetime.now(timezone.utc)
        for ordinal, field in enumerate(table.schema):
            self._dataset_column_repository.add(
                DatasetColumnMetadata(
                    id=uuid.uuid4(),
                    dataset_id=dataset.id,
                    workspace_id=dataset.workspace_id,
                    name=str(field.name),
                    data_type=str(field.type),
                    nullable=field.nullable,
                    ordinal_position=ordinal,
                    description=None,
                    is_allowed=True,
                    is_computed=False,
                    expression=None,
                    created_at=now,
                    updated_at=now,
                )
            )

    async def _get_or_create_policy(self, *, dataset: DatasetMetadata) -> DatasetPolicyMetadata:
        existing = await self._dataset_policy_repository.get_for_dataset(dataset_id=dataset.id)
        if existing is not None:
            existing.allow_dml = False
            existing.updated_at = datetime.now(timezone.utc)
            await self._dataset_policy_repository.save(existing)
            return existing
        policy = DatasetPolicyMetadata(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            workspace_id=dataset.workspace_id,
            max_rows_preview=1000,
            max_export_rows=100000,
            redaction_rules={},
            row_filters=[],
            allow_dml=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._dataset_policy_repository.add(policy)
        return policy

    async def _create_dataset_revision(
        self,
        *,
        dataset: DatasetMetadata,
        policy: DatasetPolicyMetadata,
        created_by: uuid.UUID,
        change_summary: str,
    ) -> None:
        if self._dataset_revision_repository is None:
            return
        await _flush_stores(
            self._dataset_repository,
            self._dataset_column_repository,
            self._dataset_policy_repository,
        )
        columns = await self._dataset_column_repository.list_for_dataset(dataset_id=dataset.id)
        next_revision = await self._dataset_revision_repository.next_revision_number(dataset_id=dataset.id)
        definition = self._build_dataset_definition_snapshot(dataset)
        schema_snapshot = [self._column_snapshot(column) for column in columns]
        policy_snapshot = self._policy_snapshot(policy)
        source_bindings = self._build_dataset_source_bindings(dataset)
        relation_identity, execution_capabilities = self._resolve_dataset_descriptor_snapshot(dataset)
        execution_characteristics = {
            "row_count_estimate": dataset.row_count_estimate,
            "bytes_estimate": dataset.bytes_estimate,
            "last_profiled_at": dataset.last_profiled_at.isoformat() if dataset.last_profiled_at else None,
            "relation_identity": relation_identity,
            "execution_capabilities": execution_capabilities,
        }
        snapshot = {
            "dataset": definition,
            "columns": schema_snapshot,
            "policy": policy_snapshot,
            "source_bindings": source_bindings,
            "execution_characteristics": execution_characteristics,
        }
        revision_id = uuid.uuid4()
        self._dataset_revision_repository.add(
            DatasetRevision(
                id=revision_id,
                dataset_id=dataset.id,
                workspace_id=dataset.workspace_id,
                revision_number=next_revision,
                revision_hash=stable_payload_hash(snapshot),
                change_summary=change_summary,
                definition=definition,
                schema_snapshot=schema_snapshot,
                policy=policy_snapshot,
                source_bindings=source_bindings,
                execution_characteristics=execution_characteristics,
                status=dataset.status_value,
                snapshot=snapshot,
                note=change_summary,
                created_by=created_by,
                created_at=datetime.now(timezone.utc),
            )
        )
        dataset.revision_id = revision_id

    async def _replace_dataset_lineage(self, *, dataset: DatasetMetadata) -> None:
        if self._lineage_edge_repository is None:
            return
        await self._lineage_edge_repository.delete_for_target(
            workspace_id=dataset.workspace_id,
            target_type=LineageNodeType.DATASET.value,
            target_id=str(dataset.id),
        )

        file_config = dict(dataset.file_config_json or {})
        sync_meta = dict(dataset.sync_json or {})
        sync_source = dict(sync_meta.get("source") or {})
        storage_uri = str(dataset.storage_uri or "").strip()

        edges: list[LineageEdge] = []
        if dataset.connection_id is not None:
            edges.append(
                LineageEdge(
                    workspace_id=dataset.workspace_id,
                    source_type=LineageNodeType.CONNECTION.value,
                    source_id=str(dataset.connection_id),
                    target_type=LineageNodeType.DATASET.value,
                    target_id=str(dataset.id),
                    edge_type=LineageEdgeType.FEEDS.value,
                    metadata={"connection_id": str(dataset.connection_id)},
                )
            )
        resource_name = str(sync_source.get("resource") or "").strip()
        table_name = str(sync_source.get("table") or "").strip()
        if dataset.connection_id is not None and resource_name:
            edges.append(
                LineageEdge(
                    workspace_id=dataset.workspace_id,
                    source_type=LineageNodeType.API_RESOURCE.value,
                    source_id=build_api_resource_id(
                        connection_id=dataset.connection_id,
                        resource_name=resource_name,
                    ),
                    target_type=LineageNodeType.DATASET.value,
                    target_id=str(dataset.id),
                    edge_type=LineageEdgeType.MATERIALIZES_FROM.value,
                    metadata={
                        "connection_id": str(dataset.connection_id),
                        "resource_name": resource_name,
                        "source": sync_source,
                        "strategy": sync_meta.get("strategy"),
                        "cadence": sync_meta.get("cadence"),
                    },
                )
            )
        if dataset.connection_id is not None and table_name:
            catalog_name, schema_name, base_table_name = _relation_parts(table_name)
            edges.append(
                LineageEdge(
                    workspace_id=dataset.workspace_id,
                    source_type=LineageNodeType.SOURCE_TABLE.value,
                    source_id=build_source_table_resource_id(
                        connection_id=dataset.connection_id,
                        catalog_name=catalog_name,
                        schema_name=schema_name,
                        table_name=base_table_name,
                    ),
                    target_type=LineageNodeType.DATASET.value,
                    target_id=str(dataset.id),
                    edge_type=LineageEdgeType.MATERIALIZES_FROM.value,
                    metadata={
                        "connection_id": str(dataset.connection_id),
                        "catalog_name": catalog_name,
                        "schema_name": schema_name,
                        "table_name": base_table_name,
                        "qualified_name": table_name,
                        "source": sync_source,
                        "strategy": sync_meta.get("strategy"),
                        "cadence": sync_meta.get("cadence"),
                    },
                )
            )
        if storage_uri:
            edges.append(
                LineageEdge(
                    workspace_id=dataset.workspace_id,
                    source_type=LineageNodeType.FILE_RESOURCE.value,
                    source_id=build_file_resource_id(storage_uri),
                    target_type=LineageNodeType.DATASET.value,
                    target_id=str(dataset.id),
                    edge_type=LineageEdgeType.MATERIALIZES_FROM.value,
                    metadata={
                        "storage_uri": storage_uri,
                        "file_config": file_config,
                    },
                )
            )
        for edge in edges:
            self._lineage_edge_repository.add(edge)

    @staticmethod
    def _column_snapshot(column: DatasetColumnMetadata) -> dict[str, Any]:
        return {
            "id": str(column.id),
            "dataset_id": str(column.dataset_id),
            "name": column.name,
            "data_type": column.data_type,
            "nullable": column.nullable,
            "description": column.description,
            "is_allowed": column.is_allowed,
            "is_computed": column.is_computed,
            "expression": column.expression,
            "ordinal_position": column.ordinal_position,
        }

    @staticmethod
    def _policy_snapshot(policy: DatasetPolicyMetadata) -> dict[str, Any]:
        return {
            "max_rows_preview": policy.max_rows_preview,
            "max_export_rows": policy.max_export_rows,
            "redaction_rules": dict(policy.redaction_rules_json or {}),
            "row_filters": list(policy.row_filters_json or []),
            "allow_dml": policy.allow_dml,
        }

    @staticmethod
    def _build_dataset_definition_snapshot(dataset: DatasetMetadata) -> dict[str, Any]:
        relation_identity, execution_capabilities = ConnectorSyncRuntime._resolve_dataset_descriptor_snapshot(
            dataset
        )
        return {
            "id": str(dataset.id),
            "workspace_id": str(dataset.workspace_id),
            "connection_id": str(dataset.connection_id) if dataset.connection_id else None,
            "name": dataset.name,
            "description": dataset.description,
            "tags": list(dataset.tags_json or []),
            "dataset_type": dataset.dataset_type_value,
            "materialization_mode": dataset.materialization_mode_value,
            "source": dataset.source_json,
            "sync": dataset.sync_json,
            "source_kind": dataset.source_kind_value,
            "connector_kind": dataset.connector_kind,
            "storage_kind": dataset.storage_kind_value,
            "dialect": dataset.dialect,
            "storage_uri": dataset.storage_uri,
            "catalog_name": dataset.catalog_name,
            "schema_name": dataset.schema_name,
            "table_name": dataset.table_name,
            "sql_text": dataset.sql_text,
            "referenced_dataset_ids": list(dataset.referenced_dataset_ids_json or []),
            "federated_plan": dataset.federated_plan_json,
            "file_config": dataset.file_config_json,
            "relation_identity": relation_identity,
            "execution_capabilities": execution_capabilities,
            "status": dataset.status_value,
        }

    @staticmethod
    def _build_dataset_source_bindings(dataset: DatasetMetadata) -> list[dict[str, Any]]:
        file_config = dict(dataset.file_config_json or {})
        sync_meta = dict(dataset.sync_json or {})
        storage_uri = str(dataset.storage_uri or "").strip()
        relation_identity, execution_capabilities = ConnectorSyncRuntime._resolve_dataset_descriptor_snapshot(
            dataset
        )
        bindings: list[dict[str, Any]] = [
            {
                "source_type": "dataset_contract",
                "dataset_id": str(dataset.id),
                "materialization_mode": dataset.materialization_mode_value,
                "source": dataset.source_json,
                "sync": dataset.sync_json,
                "source_kind": dataset.source_kind_value,
                "connector_kind": dataset.connector_kind,
                "storage_kind": dataset.storage_kind_value,
                "relation_identity": relation_identity,
                "execution_capabilities": execution_capabilities,
            }
        ]
        if dataset.connection_id is not None:
            bindings.append(
                {
                    "source_type": "connection",
                    "connection_id": str(dataset.connection_id),
                }
            )
        if sync_meta:
            sync_source = dict(sync_meta.get("source") or {})
            source_binding_type = "sync_source"
            if sync_source.get("resource"):
                source_binding_type = "api_resource"
            elif sync_source.get("table"):
                source_binding_type = "source_table"
            elif sync_source.get("sql"):
                source_binding_type = "sql_query"
            bindings.append(
                {
                    "source_type": source_binding_type,
                    "connection_id": str(dataset.connection_id) if dataset.connection_id else None,
                    "source": sync_source,
                    "source_key": ConnectorSyncRuntime._sync_source_key(
                        DatasetSource.model_validate(sync_source)
                    ),
                    "strategy": sync_meta.get("strategy"),
                    "cadence": sync_meta.get("cadence"),
                    "cursor_field": sync_meta.get("cursor_field"),
                }
            )
        if storage_uri:
            bindings.append(
                {
                    "source_type": "file_resource",
                    "storage_uri": storage_uri,
                    "file_config": file_config,
                }
            )
        return bindings

    @staticmethod
    def _resolve_dataset_descriptor_snapshot(dataset: DatasetMetadata) -> tuple[dict[str, Any], dict[str, Any]]:
        relation_identity = dict(dataset.relation_identity_json or {})
        execution_capabilities = dict(dataset.execution_capabilities_json or {})
        return relation_identity, execution_capabilities

    @staticmethod
    def _apply_dataset_descriptor_metadata(
        *,
        dataset: DatasetMetadata,
    ) -> None:
        if dataset.source_kind is None:
            raise ValueError("Synced datasets must set source_kind explicitly before descriptor refresh.")
        if dataset.storage_kind is None:
            raise ValueError("Synced datasets must set storage_kind explicitly before descriptor refresh.")
        if not str(dataset.connector_kind or "").strip():
            raise ValueError("Synced datasets must set connector_kind explicitly before descriptor refresh.")
        source_kind = dataset.source_kind
        storage_kind = dataset.storage_kind
        connector_kind = str(dataset.connector_kind or "").strip().lower() or None
        relation_identity = build_dataset_relation_identity(
            dataset_id=dataset.id,
            connector_id=dataset.connection_id,
            dataset_name=dataset.name,
            catalog_name=dataset.catalog_name,
            schema_name=dataset.schema_name,
            table_name=dataset.table_name,
            storage_uri=dataset.storage_uri,
            source_kind=source_kind,
            storage_kind=storage_kind,
            existing_payload=dict(dataset.relation_identity_json or {}),
        )
        execution_capabilities = build_dataset_execution_capabilities(
            source_kind=source_kind,
            storage_kind=storage_kind,
            existing_payload=dict(dataset.execution_capabilities_json or {}),
        )

        dataset.source_kind = source_kind
        dataset.connector_kind = connector_kind
        dataset.storage_kind = storage_kind
        dataset.relation_identity = relation_identity.model_dump(mode="json")
        dataset.execution_capabilities = execution_capabilities.model_dump(mode="json")

    @staticmethod
    def _dataset_description(connector_name: str, source_label: str) -> str:
        return f"Managed dataset synced from connector '{connector_name}' {source_label}."

    @staticmethod
    def _dataset_sql_alias(name: str) -> str:
        alias = _RESOURCE_SANITIZER.sub("_", str(name or "").strip().lower()).strip("_")
        alias = re.sub(r"_+", "_", alias)
        if not alias:
            return "dataset"
        if alias[0].isdigit():
            return f"dataset_{alias}"
        return alias

    @staticmethod
    def _dataset_tags(
        *,
        connector_type: ConnectorRuntimeType,
        source: DatasetSource,
    ) -> list[str]:
        if source.resource:
            return [
                "api-connector",
                connector_type.value.lower(),
                f"resource:{str(source.resource).strip().lower()}",
                "managed",
            ]
        if source.table:
            return [
                "database-connector",
                connector_type.value.lower(),
                f"table:{str(source.table).strip().lower()}",
                "managed",
            ]
        if source.sql:
            return [
                "database-connector",
                connector_type.value.lower(),
                "sql-sync",
                "managed",
            ]
        return [connector_type.value.lower(), "managed"]

    @staticmethod
    def _merge_tags(*, existing: list[str], required: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for tag in [*(existing or []), *(required or [])]:
            normalized = str(tag or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        return merged

    @staticmethod
    def _sync_meta(dataset: DatasetMetadata) -> Mapping[str, Any]:
        payload = dict(dataset.sync_json or {})
        source_payload = payload.get("source")
        if isinstance(source_payload, dict):
            merged_payload = dict(payload)
            for key, value in source_payload.items():
                merged_payload.setdefault(str(key), value)
            return merged_payload
        return payload

    @staticmethod
    def _sql_literal(value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    async def _resolve_sql_primary_key(
        self,
        *,
        sql_connector: Any,
        sync_source: DatasetSource,
        rows: list[dict[str, Any]],
    ) -> str | None:
        if sync_source.table:
            try:
                _, schema_name, table_name = _relation_parts(str(sync_source.table).strip())
                columns = await sql_connector.fetch_columns(schema_name or "public", table_name)
                for column in columns:
                    if bool(getattr(column, "is_primary_key", False)):
                        return str(getattr(column, "name"))
            except Exception:
                return None
        if rows and any("id" in row for row in rows):
            return "id"
        return None

    @staticmethod
    def _resolve_next_sql_cursor(
        *,
        rows: list[dict[str, Any]],
        cursor_field: str | None,
        current_cursor: str | None,
        sync_mode: ConnectorSyncMode,
    ) -> str | None:
        if sync_mode != ConnectorSyncMode.INCREMENTAL or not cursor_field:
            return current_cursor
        next_cursor = current_cursor
        for row in rows:
            value = row.get(cursor_field)
            if value is None or str(value).strip() == "":
                continue
            next_cursor = ConnectorSyncRuntime._pick_newer_cursor(next_cursor, str(value))
        return next_cursor

    @staticmethod
    def _dataset_parquet_path(
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        dataset_name: str,
    ) -> Path:
        return (
            Path(settings.DATASET_FILE_LOCAL_DIR)
            / "materialized"
            / str(workspace_id)
            / str(connection_id)
            / f"{dataset_name}.parquet"
        )

    @staticmethod
    def _read_existing_rows(path: Path) -> tuple[list[dict[str, Any]], pa.Schema | None]:
        if not path.exists():
            return [], None
        table = pq.read_table(path)
        return table.to_pylist(), table.schema

    @staticmethod
    def _merge_rows(
        *,
        existing_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
        primary_key: str | None,
        full_refresh: bool,
    ) -> list[dict[str, Any]]:
        if full_refresh:
            return list(new_rows)
        if not primary_key:
            return [*existing_rows, *new_rows]

        merged: dict[str, dict[str, Any]] = {}
        extras: list[dict[str, Any]] = []
        for row in existing_rows:
            key = ConnectorSyncRuntime._row_identity(row, primary_key)
            if key is None:
                extras.append(dict(row))
            else:
                merged[key] = dict(row)
        for row in new_rows:
            key = ConnectorSyncRuntime._row_identity(row, primary_key)
            if key is None:
                extras.append(dict(row))
            else:
                merged[key] = dict(row)
        return [*merged.values(), *extras]

    @staticmethod
    def _rows_to_table(*, rows: list[dict[str, Any]], existing_schema: pa.Schema | None) -> pa.Table:
        ConnectorSyncRuntime._ensure_pyarrow_compatible_pandas_stub()
        normalized_rows = ConnectorSyncRuntime._normalize_rows_for_arrow(rows)
        if normalized_rows:
            try:
                return pa.Table.from_pylist(normalized_rows)
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                stringified_rows = [
                    {key: (None if value is None else str(value)) for key, value in row.items()}
                    for row in normalized_rows
                ]
                return pa.Table.from_pylist(stringified_rows)
        if existing_schema is not None:
            return pa.Table.from_arrays(
                [pa.array([], type=field.type) for field in existing_schema],
                schema=existing_schema,
            )
        return pa.table({})

    @staticmethod
    def _ensure_pyarrow_compatible_pandas_stub() -> None:
        pandas_module = sys.modules.get("pandas")
        if pandas_module is not None and not hasattr(pandas_module, "__version__"):
            setattr(pandas_module, "__version__", "0.0.0")

    @staticmethod
    def _normalize_rows_for_arrow(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        columns: set[str] = set()
        for row in rows:
            columns.update(str(key) for key in row.keys())
        ordered_columns = sorted(columns)

        category_map: dict[str, set[str]] = {column: set() for column in ordered_columns}
        for row in rows:
            for column in ordered_columns:
                value = row.get(column)
                category = ConnectorSyncRuntime._value_category(value)
                if category is not None:
                    category_map[column].add(category)

        normalized: list[dict[str, Any]] = []
        for row in rows:
            normalized_row: dict[str, Any] = {}
            for column in ordered_columns:
                value = row.get(column)
                categories = category_map[column]
                if value is None:
                    normalized_row[column] = None
                elif categories <= {"int"}:
                    normalized_row[column] = int(value)
                elif categories <= {"int", "float"}:
                    normalized_row[column] = float(value)
                elif categories <= {"bool"}:
                    normalized_row[column] = bool(value)
                else:
                    normalized_row[column] = str(value)
            normalized.append(normalized_row)
        return normalized

    @staticmethod
    def _value_category(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        return "string"

    @staticmethod
    def _row_identity(row: dict[str, Any], primary_key: str) -> str | None:
        if primary_key == "_parent_id":
            parent_id = row.get("_parent_id")
            if parent_id is None or str(parent_id).strip() == "":
                return None
            return str(parent_id)
        if primary_key == "_child_identity":
            parent_id = row.get("_parent_id")
            child_index = row.get("_child_index")
            if parent_id is None or child_index is None:
                return None
            return f"{parent_id}:{child_index}"
        value = row.get(primary_key)
        if value is not None and str(value).strip():
            return str(value)
        return None

    @staticmethod
    def _child_primary_key(rows: list[dict[str, Any]]) -> str | None:
        if any("id" in row for row in rows):
            return "id"
        if any("_parent_id" in row for row in rows) and any("_child_index" in row for row in rows):
            return "_child_identity"
        if any("_parent_id" in row for row in rows):
            return "_parent_id"
        return None

    @staticmethod
    def _materialization_primary_key(
        *,
        resource_path: str,
        root_resource_name: str,
        root_primary_key: str | None,
        rows: list[dict[str, Any]],
    ) -> str | None:
        if resource_path == root_resource_name:
            return root_primary_key
        return ConnectorSyncRuntime._child_primary_key(rows)

    @staticmethod
    def _pick_newer_cursor(current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        if current.isdigit() and candidate.isdigit():
            return str(max(int(current), int(candidate)))
        return max(current, candidate)

    @staticmethod
    def _describe_schema_drift(
        *,
        existing_schema: pa.Schema | None,
        next_schema: pa.Schema,
    ) -> dict[str, Any] | None:
        if existing_schema is None:
            return None

        previous_fields = {field.name: str(field.type) for field in existing_schema}
        next_fields = {field.name: str(field.type) for field in next_schema}

        added_columns = sorted(name for name in next_fields if name not in previous_fields)
        removed_columns = sorted(name for name in previous_fields if name not in next_fields)
        type_changes = [
            {
                "column": name,
                "before": previous_fields[name],
                "after": next_fields[name],
            }
            for name in sorted(previous_fields.keys() & next_fields.keys())
            if previous_fields[name] != next_fields[name]
        ]
        if not added_columns and not removed_columns and not type_changes:
            return None
        return {
            "added_columns": added_columns,
            "removed_columns": removed_columns,
            "type_changes": type_changes,
        }


DatasetSyncService = ConnectorSyncRuntime
