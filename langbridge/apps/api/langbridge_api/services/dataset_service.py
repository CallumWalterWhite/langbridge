from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import yaml

from langbridge.apps.api.langbridge_api.services.connector_service import ConnectorService
from langbridge.apps.api.langbridge_api.services.jobs.dataset_job_request_service import (
    DatasetJobRequestService,
)
from langbridge.apps.api.langbridge_api.services.request_context_provider import (
    RequestContextProvider,
)
from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.datasets import (
    DatasetCatalogItem,
    DatasetCatalogResponse,
    DatasetColumnRequest,
    DatasetColumnResponse,
    DatasetCreateRequest,
    DatasetListResponse,
    DatasetPolicyRequest,
    DatasetPolicyResponse,
    DatasetPreviewColumn,
    DatasetPreviewRequest,
    DatasetPreviewResponse,
    DatasetProfileRequest,
    DatasetProfileResponse,
    DatasetResponse,
    DatasetStatsResponse,
    DatasetStatus,
    DatasetType,
    DatasetUpdateRequest,
    DatasetUsageResponse,
)
from langbridge.packages.common.langbridge_common.contracts.jobs.dataset_job import (
    CreateDatasetPreviewJobRequest,
    CreateDatasetProfileJobRequest,
)
from langbridge.packages.common.langbridge_common.db.dataset import (
    DatasetColumnRecord,
    DatasetPolicyRecord,
    DatasetRecord,
    DatasetRevisionRecord,
)
from langbridge.packages.common.langbridge_common.db.job import JobRecord, JobStatus
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
    PermissionDeniedBusinessValidationError,
    ResourceNotFound,
)
from langbridge.packages.common.langbridge_common.repositories.connector_repository import (
    ConnectorRepository,
)
from langbridge.packages.common.langbridge_common.repositories.dataset_repository import (
    DatasetColumnRepository,
    DatasetPolicyRepository,
    DatasetRepository,
    DatasetRevisionRepository,
)
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.common.langbridge_common.repositories.organization_repository import (
    OrganizationRepository,
)
from langbridge.packages.common.langbridge_common.repositories.semantic_model_repository import (
    SemanticModelRepository,
)
from langbridge.packages.common.langbridge_common.repositories.sql_repository import (
    SqlWorkspacePolicyRepository,
)
from langbridge.packages.common.langbridge_common.repositories.user_repository import (
    UserRepository,
)
from langbridge.packages.common.langbridge_common.utils.sql import (
    enforce_preview_limit,
    enforce_read_only_sql,
)
from langbridge.packages.connectors.langbridge_connectors.api.config import ConnectorRuntimeType

_FORBIDDEN_SECRET_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "client_secret",
}


class DatasetService:
    def __init__(
        self,
        *,
        dataset_repository: DatasetRepository,
        dataset_column_repository: DatasetColumnRepository,
        dataset_policy_repository: DatasetPolicyRepository,
        dataset_revision_repository: DatasetRevisionRepository,
        connector_repository: ConnectorRepository,
        semantic_model_repository: SemanticModelRepository,
        sql_workspace_policy_repository: SqlWorkspacePolicyRepository,
        organization_repository: OrganizationRepository,
        user_repository: UserRepository,
        connector_service: ConnectorService,
        dataset_job_request_service: DatasetJobRequestService,
        job_repository: JobRepository,
        request_context_provider: RequestContextProvider,
    ) -> None:
        self._dataset_repository = dataset_repository
        self._dataset_column_repository = dataset_column_repository
        self._dataset_policy_repository = dataset_policy_repository
        self._dataset_revision_repository = dataset_revision_repository
        self._connector_repository = connector_repository
        self._semantic_model_repository = semantic_model_repository
        self._sql_workspace_policy_repository = sql_workspace_policy_repository
        self._organization_repository = organization_repository
        self._user_repository = user_repository
        self._connector_service = connector_service
        self._dataset_job_request_service = dataset_job_request_service
        self._job_repository = job_repository
        self._request_context_provider = request_context_provider
        self._policy_cache_attr = "_dataset_policy_cache"

    async def list_datasets(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID | None,
        search: str | None,
        tags: list[str] | None,
        dataset_types: list[str] | None,
        current_user: UserResponse,
    ) -> DatasetListResponse:
        await self._assert_workspace_access(workspace_id, current_user)
        items = await self._dataset_repository.list_for_workspace(
            workspace_id=workspace_id,
            project_id=project_id,
            search=search,
            tags=tags or [],
            dataset_types=dataset_types or [],
        )
        results: list[DatasetResponse] = []
        for dataset in items:
            results.append(await self._to_dataset_response(dataset))
        return DatasetListResponse(items=results, total=len(results))

    async def create_dataset(
        self,
        *,
        request: DatasetCreateRequest,
        current_user: UserResponse,
    ) -> DatasetResponse:
        await self._assert_workspace_access(request.workspace_id, current_user)
        await self._assert_workspace_admin(request.workspace_id, current_user)
        self._assert_no_secret_payload(request.federated_plan, context="federated_plan")
        self._assert_no_secret_payload(request.file_config, context="file_config")
        await self._validate_dataset_feature_flags(request.dataset_type)
        await self._validate_connection_scope(
            workspace_id=request.workspace_id,
            connection_id=request.connection_id,
        )

        now = datetime.now(timezone.utc)
        dataset_id = uuid.uuid4()
        dataset = DatasetRecord(
            id=dataset_id,
            workspace_id=request.workspace_id,
            project_id=request.project_id,
            connection_id=request.connection_id,
            created_by=current_user.id,
            updated_by=current_user.id,
            name=request.name.strip(),
            description=(request.description.strip() if request.description else None),
            tags_json=[tag.strip() for tag in request.tags if tag and tag.strip()],
            dataset_type=request.dataset_type.value,
            dialect=(request.dialect.strip().lower() if request.dialect else None),
            catalog_name=request.catalog_name,
            schema_name=request.schema_name,
            table_name=request.table_name,
            sql_text=request.sql_text,
            referenced_dataset_ids_json=[str(dataset_id) for dataset_id in request.referenced_dataset_ids],
            federated_plan_json=request.federated_plan,
            file_config_json=request.file_config,
            status=request.status.value,
            revision_id=None,
            row_count_estimate=None,
            bytes_estimate=None,
            last_profiled_at=None,
            created_at=now,
            updated_at=now,
        )
        self._dataset_repository.add(dataset)

        inferred_columns = await self._resolve_create_columns(dataset=dataset, request=request)
        await self._replace_columns(
            dataset=dataset,
            workspace_id=request.workspace_id,
            columns=inferred_columns,
        )
        policy = await self._upsert_policy(dataset=dataset, policy=request.policy)
        revision_id = await self._create_revision(
            dataset=dataset,
            policy=policy,
            created_by=current_user.id,
            note="Initial dataset revision.",
        )
        dataset.revision_id = revision_id
        dataset.updated_at = datetime.now(timezone.utc)
        return await self._to_dataset_response(dataset)

    async def get_dataset(
        self,
        *,
        dataset_id: uuid.UUID,
        workspace_id: uuid.UUID,
        current_user: UserResponse,
    ) -> DatasetResponse:
        await self._assert_workspace_access(workspace_id, current_user)
        dataset = await self._get_dataset(dataset_id=dataset_id, workspace_id=workspace_id)
        return await self._to_dataset_response(dataset)

    async def update_dataset(
        self,
        *,
        dataset_id: uuid.UUID,
        request: DatasetUpdateRequest,
        current_user: UserResponse,
    ) -> DatasetResponse:
        await self._assert_workspace_access(request.workspace_id, current_user)
        await self._assert_workspace_admin(request.workspace_id, current_user)
        self._assert_no_secret_payload(request.federated_plan, context="federated_plan")
        self._assert_no_secret_payload(request.file_config, context="file_config")

        dataset = await self._get_dataset(dataset_id=dataset_id, workspace_id=request.workspace_id)

        if request.name is not None:
            dataset.name = request.name.strip()
        if request.description is not None:
            dataset.description = request.description.strip() or None
        if request.tags is not None:
            dataset.tags_json = [tag.strip() for tag in request.tags if tag and tag.strip()]
        if request.project_id is not None or "project_id" in request.model_fields_set:
            dataset.project_id = request.project_id
        if request.dialect is not None:
            dataset.dialect = request.dialect.strip().lower() if request.dialect.strip() else None
        if request.catalog_name is not None:
            dataset.catalog_name = request.catalog_name
        if request.schema_name is not None:
            dataset.schema_name = request.schema_name
        if request.table_name is not None:
            dataset.table_name = request.table_name
        if request.sql_text is not None:
            dataset.sql_text = request.sql_text
        if request.referenced_dataset_ids is not None:
            dataset.referenced_dataset_ids_json = [str(item) for item in request.referenced_dataset_ids]
        if request.federated_plan is not None or "federated_plan" in request.model_fields_set:
            dataset.federated_plan_json = request.federated_plan
        if request.file_config is not None or "file_config" in request.model_fields_set:
            dataset.file_config_json = request.file_config
        if request.status is not None:
            dataset.status = request.status.value

        if request.columns is not None:
            await self._replace_columns(
                dataset=dataset,
                workspace_id=request.workspace_id,
                columns=request.columns,
            )

        policy = await self._upsert_policy(dataset=dataset, policy=request.policy)
        revision_id = await self._create_revision(
            dataset=dataset,
            policy=policy,
            created_by=current_user.id,
            note="Dataset updated.",
        )
        dataset.revision_id = revision_id
        dataset.updated_by = current_user.id
        dataset.updated_at = datetime.now(timezone.utc)
        return await self._to_dataset_response(dataset)

    async def delete_dataset(
        self,
        *,
        dataset_id: uuid.UUID,
        workspace_id: uuid.UUID,
        current_user: UserResponse,
    ) -> None:
        await self._assert_workspace_access(workspace_id, current_user)
        await self._assert_workspace_admin(workspace_id, current_user)
        dataset = await self._get_dataset(dataset_id=dataset_id, workspace_id=workspace_id)
        await self._dataset_repository.delete(dataset)

    async def get_catalog(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID | None,
        current_user: UserResponse,
    ) -> DatasetCatalogResponse:
        await self._assert_workspace_access(workspace_id, current_user)
        datasets = await self._dataset_repository.list_for_workspace(
            workspace_id=workspace_id,
            project_id=project_id,
            limit=500,
        )
        items: list[DatasetCatalogItem] = []
        for dataset in datasets:
            columns = await self._dataset_column_repository.list_for_dataset(dataset_id=dataset.id)
            items.append(
                DatasetCatalogItem(
                    id=dataset.id,
                    name=dataset.name,
                    dataset_type=DatasetType(dataset.dataset_type.upper()),
                    tags=list(dataset.tags_json or []),
                    columns=[self._to_column_response(column) for column in columns],
                    updated_at=dataset.updated_at,
                )
            )
        return DatasetCatalogResponse(workspace_id=workspace_id, items=items)

    async def get_usage(
        self,
        *,
        dataset_id: uuid.UUID,
        workspace_id: uuid.UUID,
        current_user: UserResponse,
    ) -> DatasetUsageResponse:
        await self._assert_workspace_access(workspace_id, current_user)
        dataset = await self._get_dataset(dataset_id=dataset_id, workspace_id=workspace_id)

        semantic_models = await self._semantic_model_repository.list_for_scope(
            organization_id=workspace_id,
            project_id=dataset.project_id,
        )
        used_by_models: list[dict[str, Any]] = []
        for model in semantic_models:
            payload = self._parse_json_or_yaml(model.content_json, model.content_yaml)
            if not payload:
                continue
            tables = payload.get("tables")
            if not isinstance(tables, dict):
                continue
            matched_tables = [
                table_key
                for table_key, table_payload in tables.items()
                if isinstance(table_payload, dict)
                and str(table_payload.get("dataset_id") or table_payload.get("datasetId") or "") == str(dataset.id)
            ]
            if not matched_tables:
                continue
            used_by_models.append(
                {
                    "id": str(model.id),
                    "name": model.name,
                    "project_id": str(model.project_id) if model.project_id else None,
                    "matched_tables": matched_tables,
                }
            )

        return DatasetUsageResponse(
            semantic_models=used_by_models,
            dashboards=[],
            saved_queries=[],
        )

    async def preview_dataset(
        self,
        *,
        dataset_id: uuid.UUID,
        request: DatasetPreviewRequest,
        current_user: UserResponse,
    ) -> DatasetPreviewResponse:
        await self._assert_workspace_access(request.workspace_id, current_user)
        dataset = await self._get_dataset(dataset_id=dataset_id, workspace_id=request.workspace_id)
        policy = await self._get_or_create_policy(dataset)

        workspace_cap = await self._get_workspace_preview_cap(workspace_id=request.workspace_id)
        requested_limit = request.limit or policy.max_rows_preview
        effective_limit = min(requested_limit, policy.max_rows_preview, workspace_cap)

        job = await self._dataset_job_request_service.create_preview_job(
            CreateDatasetPreviewJobRequest(
                dataset_id=dataset.id,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                user_id=current_user.id,
                requested_limit=request.limit,
                enforced_limit=effective_limit,
                filters=request.filters,
                sort=[item.model_dump(mode="json") for item in request.sort],
                user_context=request.user_context,
                correlation_id=self._request_context_provider.correlation_id,
            )
        )

        if not request.wait_for_completion:
            return DatasetPreviewResponse(
                job_id=job.id,
                status=job.status.value,
                dataset_id=dataset.id,
                effective_limit=effective_limit,
            )

        latest_job = await self._wait_for_job(job.id, timeout_seconds=request.wait_timeout_seconds)
        if latest_job.status == JobStatus.succeeded:
            payload = latest_job.result if isinstance(latest_job.result, dict) else {}
            result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
            if result is None:
                return DatasetPreviewResponse(
                    job_id=latest_job.id,
                    status=latest_job.status.value,
                    dataset_id=dataset.id,
                    effective_limit=effective_limit,
                    error="Dataset preview job did not return a result.",
                )
            columns = [
                DatasetPreviewColumn(
                    name=str(column.get("name") or ""),
                    data_type=(str(column.get("type")) if column.get("type") is not None else None),
                )
                for column in (result.get("columns") or [])
                if isinstance(column, dict) and str(column.get("name") or "").strip()
            ]
            rows = [row for row in (result.get("rows") or []) if isinstance(row, dict)]
            return DatasetPreviewResponse(
                job_id=latest_job.id,
                status=latest_job.status.value,
                dataset_id=dataset.id,
                columns=columns,
                rows=rows,
                row_count_preview=int(result.get("row_count_preview") or len(rows)),
                effective_limit=effective_limit,
                redaction_applied=bool(result.get("redaction_applied")),
                duration_ms=(int(result["duration_ms"]) if result.get("duration_ms") is not None else None),
                bytes_scanned=(int(result["bytes_scanned"]) if result.get("bytes_scanned") is not None else None),
            )

        error = None
        if isinstance(latest_job.error, dict):
            error = str(latest_job.error.get("message") or "")
        return DatasetPreviewResponse(
            job_id=latest_job.id,
            status=latest_job.status.value,
            dataset_id=dataset.id,
            effective_limit=effective_limit,
            error=error or "Dataset preview job did not complete successfully.",
        )

    async def profile_dataset(
        self,
        *,
        dataset_id: uuid.UUID,
        request: DatasetProfileRequest,
        current_user: UserResponse,
    ) -> DatasetProfileResponse:
        await self._assert_workspace_access(request.workspace_id, current_user)
        dataset = await self._get_dataset(dataset_id=dataset_id, workspace_id=request.workspace_id)

        job = await self._dataset_job_request_service.create_profile_job(
            CreateDatasetProfileJobRequest(
                dataset_id=dataset.id,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                user_id=current_user.id,
                user_context=request.user_context,
                correlation_id=self._request_context_provider.correlation_id,
            )
        )

        if not request.wait_for_completion:
            return DatasetProfileResponse(
                job_id=job.id,
                status=job.status.value,
                dataset_id=dataset.id,
            )

        latest_job = await self._wait_for_job(job.id, timeout_seconds=request.wait_timeout_seconds)
        if latest_job.status == JobStatus.succeeded:
            payload = latest_job.result if isinstance(latest_job.result, dict) else {}
            result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
            if result is None:
                return DatasetProfileResponse(
                    job_id=latest_job.id,
                    status=latest_job.status.value,
                    dataset_id=dataset.id,
                    error="Dataset profile job did not return a result.",
                )
            profiled_at = None
            if isinstance(result.get("profiled_at"), str):
                try:
                    profiled_at = datetime.fromisoformat(str(result["profiled_at"]))
                except ValueError:
                    profiled_at = datetime.now(timezone.utc)
            return DatasetProfileResponse(
                job_id=latest_job.id,
                status=latest_job.status.value,
                dataset_id=dataset.id,
                row_count_estimate=(
                    int(result["row_count_estimate"]) if result.get("row_count_estimate") is not None else None
                ),
                bytes_estimate=(int(result["bytes_estimate"]) if result.get("bytes_estimate") is not None else None),
                distinct_counts={
                    str(key): int(value)
                    for key, value in (result.get("distinct_counts") or {}).items()
                    if value is not None
                },
                null_rates={
                    str(key): float(value)
                    for key, value in (result.get("null_rates") or {}).items()
                    if value is not None
                },
                profiled_at=profiled_at,
            )

        error = None
        if isinstance(latest_job.error, dict):
            error = str(latest_job.error.get("message") or "")
        return DatasetProfileResponse(
            job_id=latest_job.id,
            status=latest_job.status.value,
            dataset_id=dataset.id,
            error=error or "Dataset profile job did not complete successfully.",
        )

    async def _resolve_create_columns(
        self,
        *,
        dataset: DatasetRecord,
        request: DatasetCreateRequest,
    ) -> list[DatasetColumnRequest]:
        if request.columns:
            return request.columns

        if request.dataset_type == DatasetType.TABLE:
            inferred = await self._infer_columns_from_table(
                connection_id=request.connection_id,
                schema_name=request.schema_name or "",
                table_name=request.table_name or "",
            )
            if inferred:
                return inferred
        elif request.dataset_type == DatasetType.SQL:
            inferred = await self._infer_columns_from_sql(
                connection_id=request.connection_id,
                dataset_dialect=request.dialect or "tsql",
                sql_text=request.sql_text or "",
            )
            if inferred:
                return inferred

        return []

    async def _infer_columns_from_table(
        self,
        *,
        connection_id: uuid.UUID | None,
        schema_name: str,
        table_name: str,
    ) -> list[DatasetColumnRequest]:
        if connection_id is None or not table_name:
            return []
        connector = await self._connector_repository.get_by_id(connection_id)
        if connector is None:
            return []
        connector_type = getattr(connector, "connector_type", None)
        if not connector_type:
            return []

        connector_response = await self._connector_service.get_connector(connection_id)
        runtime_type = ConnectorRuntimeType(connector_type.upper())
        try:
            sql_connector = await self._connector_service.async_create_sql_connector(
                runtime_type,
                connector_response.config or {},
            )
            columns = await sql_connector.fetch_columns(schema_name, table_name)
        except Exception:
            return []

        inferred: list[DatasetColumnRequest] = []
        for index, column in enumerate(columns):
            inferred.append(
                DatasetColumnRequest(
                    name=column.name,
                    data_type=getattr(column, "data_type", "string"),
                    nullable=bool(getattr(column, "is_nullable", True)),
                    is_allowed=True,
                    ordinal_position=index,
                )
            )
        return inferred

    async def _infer_columns_from_sql(
        self,
        *,
        connection_id: uuid.UUID | None,
        dataset_dialect: str,
        sql_text: str,
    ) -> list[DatasetColumnRequest]:
        if connection_id is None or not sql_text.strip():
            return []
        connector = await self._connector_repository.get_by_id(connection_id)
        if connector is None:
            return []
        connector_type = getattr(connector, "connector_type", None)
        if not connector_type:
            return []

        connector_response = await self._connector_service.get_connector(connection_id)
        runtime_type = ConnectorRuntimeType(connector_type.upper())
        try:
            enforce_read_only_sql(sql_text, allow_dml=False, dialect=dataset_dialect)
            limited_sql, _ = enforce_preview_limit(
                sql_text,
                max_rows=1,
                dialect=dataset_dialect,
            )
            sql_connector = await self._connector_service.async_create_sql_connector(
                runtime_type,
                connector_response.config or {},
            )
            result = await sql_connector.execute(limited_sql, params={}, max_rows=1, timeout_s=10)
        except Exception:
            return []

        inferred: list[DatasetColumnRequest] = []
        for index, column_name in enumerate(result.columns):
            inferred.append(
                DatasetColumnRequest(
                    name=str(column_name),
                    data_type="unknown",
                    nullable=True,
                    is_allowed=True,
                    ordinal_position=index,
                )
            )
        return inferred

    async def _replace_columns(
        self,
        *,
        dataset: DatasetRecord,
        workspace_id: uuid.UUID,
        columns: list[DatasetColumnRequest],
    ) -> None:
        await self._dataset_column_repository.delete_for_dataset(dataset_id=dataset.id)
        for index, column in enumerate(columns):
            column_record = DatasetColumnRecord(
                id=uuid.uuid4(),
                dataset_id=dataset.id,
                workspace_id=workspace_id,
                name=column.name,
                data_type=column.data_type,
                nullable=column.nullable,
                ordinal_position=column.ordinal_position if column.ordinal_position is not None else index,
                description=column.description,
                is_allowed=column.is_allowed,
                is_computed=column.is_computed,
                expression=column.expression,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self._dataset_column_repository.add(column_record)

    async def _upsert_policy(
        self,
        *,
        dataset: DatasetRecord,
        policy: DatasetPolicyRequest | None,
    ) -> DatasetPolicyRecord:
        existing = await self._dataset_policy_repository.get_for_dataset(dataset_id=dataset.id)
        if existing is None:
            existing = DatasetPolicyRecord(
                id=uuid.uuid4(),
                dataset_id=dataset.id,
                workspace_id=dataset.workspace_id,
                max_rows_preview=settings.SQL_DEFAULT_MAX_PREVIEW_ROWS,
                max_export_rows=settings.SQL_DEFAULT_MAX_EXPORT_ROWS,
                redaction_rules_json={},
                row_filters_json=[],
                allow_dml=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self._dataset_policy_repository.add(existing)
        self._set_cached_policy(dataset, existing)

        if policy is not None:
            if policy.max_rows_preview is not None:
                existing.max_rows_preview = policy.max_rows_preview
            if policy.max_export_rows is not None:
                existing.max_export_rows = policy.max_export_rows
            if policy.redaction_rules is not None:
                existing.redaction_rules_json = dict(policy.redaction_rules)
            if policy.row_filters is not None:
                existing.row_filters_json = list(policy.row_filters)
            if policy.allow_dml is not None:
                existing.allow_dml = bool(policy.allow_dml)
            existing.updated_at = datetime.now(timezone.utc)

        return existing

    async def _create_revision(
        self,
        *,
        dataset: DatasetRecord,
        policy: DatasetPolicyRecord,
        created_by: uuid.UUID,
        note: str,
    ) -> uuid.UUID:
        columns = await self._dataset_column_repository.list_for_dataset(dataset_id=dataset.id)
        next_revision = await self._dataset_revision_repository.next_revision_number(dataset_id=dataset.id)
        snapshot = {
            "dataset": {
                "id": str(dataset.id),
                "workspace_id": str(dataset.workspace_id),
                "project_id": str(dataset.project_id) if dataset.project_id else None,
                "connection_id": str(dataset.connection_id) if dataset.connection_id else None,
                "name": dataset.name,
                "description": dataset.description,
                "tags": list(dataset.tags_json or []),
                "dataset_type": dataset.dataset_type,
                "dialect": dataset.dialect,
                "catalog_name": dataset.catalog_name,
                "schema_name": dataset.schema_name,
                "table_name": dataset.table_name,
                "sql_text": dataset.sql_text,
                "referenced_dataset_ids": list(dataset.referenced_dataset_ids_json or []),
                "federated_plan": dataset.federated_plan_json,
                "file_config": dataset.file_config_json,
                "status": dataset.status,
            },
            "columns": [self._to_column_response(column).model_dump(mode="json") for column in columns],
            "policy": self._to_policy_response(policy).model_dump(mode="json"),
        }
        revision_id = uuid.uuid4()
        self._dataset_revision_repository.add(
            DatasetRevisionRecord(
                id=revision_id,
                dataset_id=dataset.id,
                workspace_id=dataset.workspace_id,
                revision_number=next_revision,
                snapshot_json=snapshot,
                note=note,
                created_by=created_by,
                created_at=datetime.now(timezone.utc),
            )
        )
        return revision_id

    async def _to_dataset_response(self, dataset: DatasetRecord) -> DatasetResponse:
        columns = await self._dataset_column_repository.list_for_dataset(dataset_id=dataset.id)
        policy = await self._get_or_create_policy(dataset)
        return DatasetResponse(
            id=dataset.id,
            workspace_id=dataset.workspace_id,
            project_id=dataset.project_id,
            connection_id=dataset.connection_id,
            name=dataset.name,
            description=dataset.description,
            tags=list(dataset.tags_json or []),
            dataset_type=DatasetType(dataset.dataset_type.upper()),
            dialect=dataset.dialect,
            catalog_name=dataset.catalog_name,
            schema_name=dataset.schema_name,
            table_name=dataset.table_name,
            sql_text=dataset.sql_text,
            referenced_dataset_ids=[
                uuid.UUID(value) for value in (dataset.referenced_dataset_ids_json or []) if value
            ],
            federated_plan=dataset.federated_plan_json,
            file_config=dataset.file_config_json,
            status=DatasetStatus(dataset.status),
            revision_id=dataset.revision_id,
            columns=[self._to_column_response(column) for column in columns],
            policy=self._to_policy_response(policy),
            stats=DatasetStatsResponse(
                row_count_estimate=dataset.row_count_estimate,
                bytes_estimate=dataset.bytes_estimate,
                last_profiled_at=dataset.last_profiled_at,
            ),
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )

    async def _get_dataset(self, *, dataset_id: uuid.UUID, workspace_id: uuid.UUID) -> DatasetRecord:
        dataset = await self._dataset_repository.get_for_workspace(
            dataset_id=dataset_id,
            workspace_id=workspace_id,
        )
        if dataset is None:
            raise ResourceNotFound("Dataset not found.")
        return dataset

    async def _get_or_create_policy(self, dataset: DatasetRecord) -> DatasetPolicyRecord:
        cached_policy = self._get_cached_policy(dataset)
        if cached_policy is not None:
            return cached_policy
        policy = await self._dataset_policy_repository.get_for_dataset(dataset_id=dataset.id)
        if policy is not None:
            self._set_cached_policy(dataset, policy)
            return policy
        policy = DatasetPolicyRecord(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            workspace_id=dataset.workspace_id,
            max_rows_preview=settings.SQL_DEFAULT_MAX_PREVIEW_ROWS,
            max_export_rows=settings.SQL_DEFAULT_MAX_EXPORT_ROWS,
            redaction_rules_json={},
            row_filters_json=[],
            allow_dml=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._set_cached_policy(dataset, policy)
        self._dataset_policy_repository.add(policy)
        return policy

    def _get_cached_policy(self, dataset: DatasetRecord) -> DatasetPolicyRecord | None:
        cached = getattr(dataset, self._policy_cache_attr, None)
        if isinstance(cached, DatasetPolicyRecord):
            return cached
        return None

    def _set_cached_policy(self, dataset: DatasetRecord, policy: DatasetPolicyRecord) -> None:
        setattr(dataset, self._policy_cache_attr, policy)

    def _to_column_response(self, column: DatasetColumnRecord) -> DatasetColumnResponse:
        return DatasetColumnResponse(
            id=column.id,
            dataset_id=column.dataset_id,
            name=column.name,
            data_type=column.data_type,
            nullable=column.nullable,
            description=column.description,
            is_allowed=column.is_allowed,
            is_computed=column.is_computed,
            expression=column.expression,
            ordinal_position=column.ordinal_position,
        )

    @staticmethod
    def _to_policy_response(policy: DatasetPolicyRecord) -> DatasetPolicyResponse:
        return DatasetPolicyResponse(
            max_rows_preview=policy.max_rows_preview,
            max_export_rows=policy.max_export_rows,
            redaction_rules=dict(policy.redaction_rules_json or {}),
            row_filters=list(policy.row_filters_json or []),
            allow_dml=policy.allow_dml,
        )

    async def _get_workspace_preview_cap(self, *, workspace_id: uuid.UUID) -> int:
        sql_policy = await self._sql_workspace_policy_repository.get_by_workspace_id(
            workspace_id=workspace_id
        )
        if sql_policy is not None:
            return sql_policy.max_preview_rows
        return settings.SQL_DEFAULT_MAX_PREVIEW_ROWS

    async def _wait_for_job(self, job_id: uuid.UUID, *, timeout_seconds: int) -> JobRecord:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        last_seen: JobRecord | None = None
        while loop.time() <= deadline:
            current = await self._job_repository.get_by_id(job_id)
            if current is None:
                raise ResourceNotFound("Dataset execution job not found.")
            last_seen = current
            if current.status in {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}:
                return current
            await asyncio.sleep(0.5)
        if last_seen is None:
            raise ResourceNotFound("Dataset execution job not found.")
        return last_seen

    async def _assert_workspace_access(
        self,
        workspace_id: uuid.UUID,
        current_user: UserResponse,
    ) -> None:
        if self._is_internal_user(current_user):
            return
        allowed = {str(item) for item in (current_user.available_organizations or [])}
        if str(workspace_id) not in allowed:
            raise PermissionDeniedBusinessValidationError("Forbidden")

    async def _assert_workspace_admin(
        self,
        workspace_id: uuid.UUID,
        current_user: UserResponse,
    ) -> None:
        if self._is_internal_user(current_user):
            return
        organization = await self._organization_repository.get_by_id(workspace_id)
        if organization is None:
            raise ResourceNotFound("Workspace not found.")
        user = await self._user_repository.get_by_id(current_user.id)
        if user is None:
            raise ResourceNotFound("User not found.")
        role = await self._organization_repository.get_member_role(organization, user)
        if role not in {"owner", "admin"}:
            raise PermissionDeniedBusinessValidationError(
                "Dataset create/update/delete requires workspace admin permissions."
            )

    async def _validate_connection_scope(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID | None,
    ) -> None:
        if connection_id is None:
            return
        connector = await self._connector_repository.get_by_id(connection_id)
        if connector is None:
            raise ResourceNotFound("Connection not found.")
        if not self._connector_is_in_workspace(connector, workspace_id):
            raise PermissionDeniedBusinessValidationError("Connection does not belong to this workspace.")

    async def _validate_dataset_feature_flags(self, dataset_type: DatasetType) -> None:
        if dataset_type == DatasetType.FEDERATED and not settings.SQL_FEDERATION_ENABLED:
            raise BusinessValidationError("Federated datasets are disabled in this deployment.")
        if dataset_type == DatasetType.FILE and not getattr(settings, "DATASET_FILE_ENABLED", False):
            raise BusinessValidationError("File datasets are disabled in this deployment.")

    def _assert_no_secret_payload(self, payload: Any, *, context: str) -> None:
        if payload is None:
            return
        if isinstance(payload, dict):
            for key, value in payload.items():
                lowered = str(key).strip().lower()
                if lowered in _FORBIDDEN_SECRET_KEYS and value not in {None, ""}:
                    raise BusinessValidationError(
                        f"{context} must not include secret field '{key}'."
                    )
                self._assert_no_secret_payload(value, context=context)
            return
        if isinstance(payload, list):
            for item in payload:
                self._assert_no_secret_payload(item, context=context)

    @staticmethod
    def _connector_is_in_workspace(connector: Any, workspace_id: uuid.UUID) -> bool:
        organizations = getattr(connector, "organizations", None) or []
        return any(str(getattr(org, "id", "")) == str(workspace_id) for org in organizations)

    @staticmethod
    def _is_internal_user(user: UserResponse) -> bool:
        return user.id.int == 0

    @staticmethod
    def _parse_json_or_yaml(
        content_json: str | None,
        content_yaml: str | None,
    ) -> dict[str, Any] | None:
        if content_json:
            try:
                parsed = json.loads(content_json)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        if content_yaml:
            try:
                parsed_yaml = yaml.safe_load(content_yaml)
                if isinstance(parsed_yaml, dict):
                    return parsed_yaml
            except Exception:
                return None
        return None
