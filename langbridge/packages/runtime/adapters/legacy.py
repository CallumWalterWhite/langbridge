from __future__ import annotations

import json
from typing import Any

from langbridge.packages.runtime.models import (
    ConnectionMetadata,
    ConnectionPolicy,
    ConnectorMetadata,
    ConnectorSyncState,
    DatasetColumnMetadata,
    DatasetMetadata,
    DatasetPolicyMetadata,
    SecretReference,
    SemanticModelMetadata,
    SqlJobResultArtifact,
)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(exclude_none=True)
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _resolve_org_id(value: Any) -> Any:
    if getattr(value, "organization_id", None) is not None:
        return value.organization_id
    organizations = getattr(value, "organizations", None) or []
    if organizations:
        return getattr(organizations[0], "id", None)
    return None


def _resolve_project_id(value: Any) -> Any:
    if getattr(value, "project_id", None) is not None:
        return value.project_id
    projects = getattr(value, "projects", None) or []
    if projects:
        return getattr(projects[0], "id", None)
    return None


def to_runtime_secret_reference(value: Any) -> SecretReference:
    if isinstance(value, SecretReference):
        return value
    return SecretReference.model_validate(value)


def to_runtime_connection_metadata(value: Any | None) -> ConnectionMetadata | None:
    if value is None:
        return None
    if isinstance(value, ConnectionMetadata):
        return value
    payload = _as_dict(value)
    if not payload:
        return None
    return ConnectionMetadata.model_validate(payload)


def to_runtime_connection_policy(value: Any | None) -> ConnectionPolicy | None:
    if value is None:
        return None
    if isinstance(value, ConnectionPolicy):
        return value
    payload = _as_dict(value)
    if not payload:
        return None
    return ConnectionPolicy.model_validate(payload)


def to_runtime_connector(value: Any | None) -> ConnectorMetadata | None:
    if value is None:
        return None
    if isinstance(value, ConnectorMetadata):
        return value
    config = getattr(value, "config", None)
    if config is None:
        config = _as_dict(getattr(value, "config_json", None))
    secret_refs_raw = getattr(value, "secret_references", None)
    if secret_refs_raw is None:
        secret_refs_raw = getattr(value, "secret_references_json", None) or {}
    secret_references = {
        str(key): to_runtime_secret_reference(item)
        for key, item in dict(secret_refs_raw or {}).items()
    }
    return ConnectorMetadata(
        id=getattr(value, "id"),
        name=str(getattr(value, "name")),
        description=getattr(value, "description", None),
        version=getattr(value, "version", None),
        label=getattr(value, "label", None) or getattr(value, "name", None),
        icon=getattr(value, "icon", None),
        connector_type=getattr(value, "connector_type", None),
        organization_id=_resolve_org_id(value),
        project_id=_resolve_project_id(value),
        config=config or None,
        connection_metadata=to_runtime_connection_metadata(
            getattr(value, "connection_metadata", None)
            or getattr(value, "connection_metadata_json", None)
        ),
        secret_references=secret_references,
        connection_policy=to_runtime_connection_policy(
            getattr(value, "connection_policy", None)
            or getattr(value, "access_policy_json", None)
        ),
        is_managed=bool(getattr(value, "is_managed", False)),
    )


def to_runtime_dataset_column(value: Any) -> DatasetColumnMetadata:
    if isinstance(value, DatasetColumnMetadata):
        return value
    return DatasetColumnMetadata(
        id=getattr(value, "id"),
        dataset_id=getattr(value, "dataset_id"),
        name=str(getattr(value, "name")),
        data_type=str(getattr(value, "data_type")),
        nullable=bool(getattr(value, "nullable", True)),
        description=getattr(value, "description", None),
        is_allowed=bool(getattr(value, "is_allowed", True)),
        is_computed=bool(getattr(value, "is_computed", False)),
        expression=getattr(value, "expression", None),
        ordinal_position=int(getattr(value, "ordinal_position", 0) or 0),
    )


def to_runtime_dataset_policy(value: Any | None) -> DatasetPolicyMetadata | None:
    if value is None:
        return None
    if isinstance(value, DatasetPolicyMetadata):
        return value
    return DatasetPolicyMetadata(
        id=getattr(value, "id", None),
        dataset_id=getattr(value, "dataset_id", None),
        workspace_id=getattr(value, "workspace_id", None),
        max_rows_preview=int(getattr(value, "max_rows_preview", 1000) or 1000),
        max_export_rows=int(getattr(value, "max_export_rows", 10000) or 10000),
        redaction_rules=dict(
            getattr(value, "redaction_rules", None)
            or getattr(value, "redaction_rules_json", None)
            or {}
        ),
        row_filters=list(
            getattr(value, "row_filters", None)
            or getattr(value, "row_filters_json", None)
            or []
        ),
        allow_dml=bool(getattr(value, "allow_dml", False)),
    )


def to_runtime_dataset(value: Any | None) -> DatasetMetadata | None:
    if value is None:
        return None
    if isinstance(value, DatasetMetadata):
        return value
    columns_raw = getattr(value, "columns", None) or []
    return DatasetMetadata(
        id=getattr(value, "id"),
        workspace_id=getattr(value, "workspace_id"),
        project_id=getattr(value, "project_id", None),
        connection_id=getattr(value, "connection_id", None),
        owner_id=getattr(value, "owner_id", None) or getattr(value, "created_by", None),
        created_by=getattr(value, "created_by", None),
        updated_by=getattr(value, "updated_by", None),
        name=str(getattr(value, "name")),
        sql_alias=str(getattr(value, "sql_alias")),
        description=getattr(value, "description", None),
        tags=list(getattr(value, "tags", None) or getattr(value, "tags_json", None) or []),
        dataset_type=str(getattr(value, "dataset_type")),
        source_kind=getattr(value, "source_kind", None),
        connector_kind=getattr(value, "connector_kind", None),
        storage_kind=getattr(value, "storage_kind", None),
        dialect=getattr(value, "dialect", None),
        catalog_name=getattr(value, "catalog_name", None),
        schema_name=getattr(value, "schema_name", None),
        table_name=getattr(value, "table_name", None),
        storage_uri=getattr(value, "storage_uri", None),
        sql_text=getattr(value, "sql_text", None),
        relation_identity=(
            getattr(value, "relation_identity", None)
            or getattr(value, "relation_identity_json", None)
        ),
        execution_capabilities=(
            getattr(value, "execution_capabilities", None)
            or getattr(value, "execution_capabilities_json", None)
        ),
        referenced_dataset_ids=list(
            getattr(value, "referenced_dataset_ids", None)
            or getattr(value, "referenced_dataset_ids_json", None)
            or []
        ),
        federated_plan=(
            getattr(value, "federated_plan", None)
            or getattr(value, "federated_plan_json", None)
        ),
        file_config=getattr(value, "file_config", None) or getattr(value, "file_config_json", None),
        status=str(getattr(value, "status", "published") or "published"),
        revision_id=getattr(value, "revision_id", None),
        row_count_estimate=getattr(value, "row_count_estimate", None),
        bytes_estimate=getattr(value, "bytes_estimate", None),
        last_profiled_at=getattr(value, "last_profiled_at", None),
        columns=[to_runtime_dataset_column(column) for column in columns_raw],
        policy=to_runtime_dataset_policy(getattr(value, "policy", None)),
        created_at=getattr(value, "created_at", None),
        updated_at=getattr(value, "updated_at", None),
    )


def to_runtime_semantic_model(value: Any | None) -> SemanticModelMetadata | None:
    if value is None:
        return None
    if isinstance(value, SemanticModelMetadata):
        return value
    content_json = getattr(value, "content_json", None)
    if isinstance(content_json, str):
        try:
            parsed = json.loads(content_json)
        except json.JSONDecodeError:
            parsed = content_json
        content_json = parsed
    return SemanticModelMetadata(
        id=getattr(value, "id"),
        connector_id=getattr(value, "connector_id", None),
        organization_id=getattr(value, "organization_id"),
        project_id=getattr(value, "project_id", None),
        name=str(getattr(value, "name")),
        description=getattr(value, "description", None),
        content_yaml=str(getattr(value, "content_yaml")),
        content_json=content_json,
        created_at=getattr(value, "created_at", None),
        updated_at=getattr(value, "updated_at", None),
    )


def to_runtime_sync_state(value: Any | None) -> ConnectorSyncState | None:
    if value is None:
        return None
    if isinstance(value, ConnectorSyncState):
        return value
    dataset_ids = getattr(value, "dataset_ids", None)
    if dataset_ids is None:
        dataset_ids = getattr(value, "dataset_ids_json", None) or []
    return ConnectorSyncState(
        id=getattr(value, "id"),
        workspace_id=getattr(value, "workspace_id"),
        connection_id=getattr(value, "connection_id"),
        connector_type=str(getattr(value, "connector_type")),
        resource_name=str(getattr(value, "resource_name")),
        sync_mode=str(getattr(value, "sync_mode", "INCREMENTAL")),
        last_cursor=getattr(value, "last_cursor", None),
        last_sync_at=getattr(value, "last_sync_at", None),
        state=dict(getattr(value, "state", None) or getattr(value, "state_json", None) or {}),
        status=str(getattr(value, "status", "never_synced")),
        error_message=getattr(value, "error_message", None),
        records_synced=int(getattr(value, "records_synced", 0) or 0),
        bytes_synced=getattr(value, "bytes_synced", None),
        dataset_ids=list(dataset_ids),
        created_at=getattr(value, "created_at", None),
        updated_at=getattr(value, "updated_at", None),
    )


def to_runtime_sql_job_result_artifact(value: Any | None) -> SqlJobResultArtifact | None:
    if value is None:
        return None
    if isinstance(value, SqlJobResultArtifact):
        return value
    return SqlJobResultArtifact(
        id=getattr(value, "id"),
        sql_job_id=getattr(value, "sql_job_id"),
        workspace_id=getattr(value, "workspace_id"),
        created_by=getattr(value, "created_by"),
        format=str(getattr(value, "format")),
        mime_type=str(getattr(value, "mime_type")),
        row_count=int(getattr(value, "row_count", 0) or 0),
        byte_size=getattr(value, "byte_size", None),
        storage_backend=str(getattr(value, "storage_backend")),
        storage_reference=str(getattr(value, "storage_reference")),
        payload=getattr(value, "payload", None) or getattr(value, "payload_json", None),
        created_at=getattr(value, "created_at", None),
    )
