from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlglot
from pydantic import ValidationError
from sqlglot import exp

from langbridge.apps.worker.langbridge_worker.tools import FederatedQueryTool
from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.common.langbridge_common.contracts.jobs.dataset_job import (
    CreateDatasetPreviewJobRequest,
    CreateDatasetProfileJobRequest,
)
from langbridge.packages.common.langbridge_common.contracts.jobs.type import JobType
from langbridge.packages.common.langbridge_common.db.dataset import (
    DatasetColumnRecord,
    DatasetPolicyRecord,
    DatasetRecord,
)
from langbridge.packages.common.langbridge_common.db.job import JobRecord, JobStatus
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
)
from langbridge.packages.common.langbridge_common.repositories.dataset_repository import (
    DatasetColumnRepository,
    DatasetPolicyRepository,
    DatasetRepository,
)
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.common.langbridge_common.utils.sql import (
    apply_result_redaction,
    enforce_read_only_sql,
    render_sql_with_params,
    sanitize_sql_error_message,
)
from langbridge.packages.federation.models import FederationWorkflow, VirtualDataset, VirtualTableBinding
from langbridge.packages.messaging.langbridge_messaging.contracts.base import MessageType
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.dataset_job import (
    DatasetJobRequestMessage,
)
from langbridge.packages.messaging.langbridge_messaging.handler import BaseMessageHandler


_DEFAULT_PROFILE_COLUMN_LIMIT = 5


class DatasetJobRequestHandler(BaseMessageHandler):
    message_type: MessageType = MessageType.DATASET_JOB_REQUEST

    def __init__(
        self,
        job_repository: JobRepository,
        dataset_repository: DatasetRepository,
        dataset_column_repository: DatasetColumnRepository,
        dataset_policy_repository: DatasetPolicyRepository,
        federated_query_tool: FederatedQueryTool | None = None,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._job_repository = job_repository
        self._dataset_repository = dataset_repository
        self._dataset_column_repository = dataset_column_repository
        self._dataset_policy_repository = dataset_policy_repository
        self._federated_query_tool = federated_query_tool

    async def handle(self, payload: DatasetJobRequestMessage) -> None:
        if self._federated_query_tool is None:
            raise BusinessValidationError("Federated query tool is not configured on this worker.")

        job_record = await self._job_repository.get_by_id(payload.job_id)
        if job_record is None:
            raise BusinessValidationError(f"Job with ID {payload.job_id} does not exist.")
        if job_record.status in {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}:
            self._logger.info("Dataset job %s already terminal (%s).", job_record.id, job_record.status)
            return None

        job_record.status = JobStatus.running
        job_record.progress = 5
        job_record.status_message = "Dataset execution started."
        if job_record.started_at is None:
            job_record.started_at = datetime.now(timezone.utc)

        try:
            if payload.job_type == JobType.DATASET_PREVIEW:
                request = self._parse_preview_request(payload)
                result = await self._run_preview(request)
                summary = f"Dataset preview completed with {int(result.get('row_count_preview') or 0)} rows."
            elif payload.job_type == JobType.DATASET_PROFILE:
                request = self._parse_profile_request(payload)
                result = await self._run_profile(request)
                summary = "Dataset profiling completed."
            else:
                raise BusinessValidationError(f"Unsupported dataset job type '{payload.job_type.value}'.")

            job_record.result = {
                "result": result,
                "summary": summary,
            }
            job_record.status = JobStatus.succeeded
            job_record.progress = 100
            job_record.status_message = summary
            job_record.finished_at = datetime.now(timezone.utc)
            job_record.error = None
        except Exception as exc:
            self._logger.exception("Dataset job %s failed: %s", job_record.id, exc)
            job_record.status = JobStatus.failed
            job_record.progress = 100
            job_record.status_message = "Dataset execution failed."
            job_record.finished_at = datetime.now(timezone.utc)
            job_record.error = {"message": sanitize_sql_error_message(str(exc))}

        return None

    def _parse_preview_request(self, payload: DatasetJobRequestMessage) -> CreateDatasetPreviewJobRequest:
        try:
            return CreateDatasetPreviewJobRequest.model_validate(payload.job_request)
        except ValidationError as exc:
            raise BusinessValidationError("Invalid dataset preview request payload.") from exc

    def _parse_profile_request(self, payload: DatasetJobRequestMessage) -> CreateDatasetProfileJobRequest:
        try:
            return CreateDatasetProfileJobRequest.model_validate(payload.job_request)
        except ValidationError as exc:
            raise BusinessValidationError("Invalid dataset profile request payload.") from exc

    async def _run_preview(self, request: CreateDatasetPreviewJobRequest) -> dict[str, Any]:
        dataset, columns, policy = await self._load_dataset_bundle(
            dataset_id=request.dataset_id,
            workspace_id=request.workspace_id,
        )
        effective_limit = min(max(1, request.enforced_limit), max(1, policy.max_rows_preview))

        workflow, table_key, dialect = self._build_workflow(dataset=dataset)
        preview_sql = self._build_preview_sql(
            table_key=table_key,
            columns=columns,
            policy=policy,
            request=request,
            effective_limit=effective_limit,
            dialect=dialect,
        )
        execution = await self._federated_query_tool.execute_federated_query(
            {
                "workspace_id": str(request.workspace_id),
                "query": preview_sql,
                "dialect": dialect,
                "workflow": workflow.model_dump(mode="json"),
            }
        )

        rows_payload = execution.get("rows") or []
        rows = [row for row in rows_payload if isinstance(row, dict)]
        redacted_rows, redaction_applied = apply_result_redaction(
            rows=rows,
            redaction_rules=dict(policy.redaction_rules_json or {}),
        )

        execution_meta = self._extract_execution_meta(execution)
        selected_columns = [
            {"name": column.name, "type": column.data_type}
            for column in columns
            if column.is_allowed
        ]
        if not selected_columns:
            selected_columns = [
                {"name": str(name), "type": None}
                for name in (execution.get("columns") or [])
                if str(name).strip()
            ]

        return {
            "dataset_id": str(dataset.id),
            "columns": selected_columns,
            "rows": redacted_rows,
            "row_count_preview": len(redacted_rows),
            "effective_limit": effective_limit,
            "redaction_applied": redaction_applied,
            "duration_ms": execution_meta["duration_ms"],
            "bytes_scanned": execution_meta["bytes_scanned"],
            "query_sql": preview_sql,
        }

    async def _run_profile(self, request: CreateDatasetProfileJobRequest) -> dict[str, Any]:
        dataset, columns, policy = await self._load_dataset_bundle(
            dataset_id=request.dataset_id,
            workspace_id=request.workspace_id,
        )
        workflow, table_key, dialect = self._build_workflow(dataset=dataset)

        base_filters = self._build_row_filter_expressions(
            policy=policy,
            request_context=request.user_context,
            workspace_id=request.workspace_id,
            project_id=request.project_id,
            user_id=request.user_id,
            dialect=dialect,
        )
        count_sql = self._build_count_sql(table_key=table_key, filters=base_filters, dialect=dialect)
        count_execution = await self._federated_query_tool.execute_federated_query(
            {
                "workspace_id": str(request.workspace_id),
                "query": count_sql,
                "dialect": dialect,
                "workflow": workflow.model_dump(mode="json"),
            }
        )
        row_count_estimate = self._extract_single_numeric(
            count_execution,
            preferred_keys=["row_count", "count", "rowcount"],
        )

        profiled_columns = [
            column
            for column in columns
            if column.is_allowed and not column.is_computed
        ][: _DEFAULT_PROFILE_COLUMN_LIMIT]
        distinct_counts: dict[str, int] = {}
        null_rates: dict[str, float] = {}
        for column in profiled_columns:
            stats_sql = self._build_column_profile_sql(
                table_key=table_key,
                column_name=column.name,
                filters=base_filters,
                dialect=dialect,
            )
            stats_execution = await self._federated_query_tool.execute_federated_query(
                {
                    "workspace_id": str(request.workspace_id),
                    "query": stats_sql,
                    "dialect": dialect,
                    "workflow": workflow.model_dump(mode="json"),
                }
            )
            distinct_count = self._extract_single_numeric(
                stats_execution,
                preferred_keys=["distinct_count", "distinct"],
            )
            null_count = self._extract_single_numeric(
                stats_execution,
                preferred_keys=["null_count", "nulls"],
            )
            if distinct_count is not None:
                distinct_counts[column.name] = distinct_count
            if row_count_estimate and row_count_estimate > 0 and null_count is not None:
                null_rates[column.name] = float(null_count) / float(row_count_estimate)

        execution_meta = self._extract_execution_meta(count_execution)
        now = datetime.now(timezone.utc)
        dataset.row_count_estimate = row_count_estimate
        dataset.bytes_estimate = execution_meta["bytes_scanned"]
        dataset.last_profiled_at = now
        dataset.updated_at = now

        return {
            "dataset_id": str(dataset.id),
            "row_count_estimate": row_count_estimate,
            "bytes_estimate": execution_meta["bytes_scanned"],
            "distinct_counts": distinct_counts,
            "null_rates": null_rates,
            "profiled_at": now.isoformat(),
        }

    async def _load_dataset_bundle(
        self,
        *,
        dataset_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> tuple[DatasetRecord, list[DatasetColumnRecord], DatasetPolicyRecord]:
        dataset = await self._dataset_repository.get_for_workspace(
            dataset_id=dataset_id,
            workspace_id=workspace_id,
        )
        if dataset is None:
            raise BusinessValidationError("Dataset not found.")
        columns = await self._dataset_column_repository.list_for_dataset(dataset_id=dataset.id)
        policy = await self._dataset_policy_repository.get_for_dataset(dataset_id=dataset.id)
        if policy is None:
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
            self._dataset_policy_repository.add(policy)
        return dataset, columns, policy

    def _build_workflow(self, *, dataset: DatasetRecord) -> tuple[FederationWorkflow, str, str]:
        dataset_type = str(dataset.dataset_type or "").upper()
        if dataset_type not in {"TABLE", "SQL"}:
            raise BusinessValidationError(
                f"Dataset type '{dataset.dataset_type}' is not executable in this runtime yet."
            )
        if dataset.connection_id is None:
            raise BusinessValidationError("Executable datasets require a connection_id.")

        dialect = (dataset.dialect or "tsql").strip().lower() or "tsql"
        table_key = "dataset_source"
        metadata: dict[str, Any] = {
            "physical_catalog": dataset.catalog_name,
            "physical_schema": dataset.schema_name,
            "physical_table": dataset.table_name,
        }
        binding_table_name = dataset.table_name or "dataset_source"
        schema_name = dataset.schema_name
        catalog_name = dataset.catalog_name

        if dataset_type == "SQL":
            sql_text = (dataset.sql_text or "").strip()
            if not sql_text:
                raise BusinessValidationError("SQL dataset is missing sql_text.")
            enforce_read_only_sql(sql_text, allow_dml=False, dialect=dialect)
            metadata = {
                "physical_sql": sql_text,
                "sql_dialect": dialect,
            }
            binding_table_name = "dataset_sql"
            schema_name = None
            catalog_name = None

        workflow = FederationWorkflow(
            id=f"workflow_dataset_{dataset.id.hex[:12]}",
            workspace_id=str(dataset.workspace_id),
            dataset=VirtualDataset(
                id=f"dataset_{dataset.id.hex[:12]}",
                name=dataset.name,
                workspace_id=str(dataset.workspace_id),
                tables={
                    table_key: VirtualTableBinding(
                        table_key=table_key,
                        source_id=f"source_{dataset.connection_id.hex[:12]}",
                        connector_id=dataset.connection_id,
                        schema=schema_name,
                        table=binding_table_name,
                        catalog=catalog_name,
                        metadata=metadata,
                    )
                },
                relationships=[],
            ),
            broadcast_threshold_bytes=settings.FEDERATION_BROADCAST_THRESHOLD_BYTES,
            partition_count=settings.FEDERATION_PARTITION_COUNT,
            max_stage_retries=settings.FEDERATION_STAGE_MAX_RETRIES,
            stage_parallelism=settings.FEDERATION_STAGE_PARALLELISM,
        )
        return workflow, table_key, dialect

    def _build_preview_sql(
        self,
        *,
        table_key: str,
        columns: list[DatasetColumnRecord],
        policy: DatasetPolicyRecord,
        request: CreateDatasetPreviewJobRequest,
        effective_limit: int,
        dialect: str,
    ) -> str:
        select_expr = exp.select()
        allowed_columns = [column for column in columns if column.is_allowed]

        if not allowed_columns:
            select_expr = select_expr.select(exp.Star())
        else:
            projections: list[exp.Expression] = []
            for column in allowed_columns:
                if column.is_computed and column.expression:
                    try:
                        parsed_expression = sqlglot.parse_one(column.expression, read=dialect)
                        projections.append(exp.alias_(parsed_expression, column.name, quoted=True))
                    except sqlglot.ParseError:
                        continue
                    continue
                projections.append(
                    exp.Column(this=exp.Identifier(this=column.name, quoted=True))
                )
            if projections:
                select_expr = select_expr.select(*projections)
            else:
                select_expr = select_expr.select(exp.Star())

        select_expr = select_expr.from_(exp.table_(table_key, quoted=False))

        filter_expressions = self._build_filter_expressions(
            filters=request.filters,
            allowed_columns=allowed_columns,
            dialect=dialect,
        )
        filter_expressions.extend(
            self._build_row_filter_expressions(
                policy=policy,
                request_context=request.user_context,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                user_id=request.user_id,
                dialect=dialect,
            )
        )
        if filter_expressions:
            select_expr = select_expr.where(exp.and_(*filter_expressions))

        order_items: list[exp.Ordered] = []
        allowed_names = {column.name.lower() for column in allowed_columns}
        for item in request.sort:
            column = str(item.get("column") or "").strip()
            direction = str(item.get("direction") or "asc").strip().lower()
            if not column:
                continue
            if allowed_names and column.lower() not in allowed_names:
                continue
            order_items.append(
                exp.Ordered(
                    this=exp.Column(this=exp.Identifier(this=column, quoted=True)),
                    desc=direction == "desc",
                )
            )
        if order_items:
            select_expr = select_expr.order_by(*order_items)

        select_expr = select_expr.limit(effective_limit)
        return select_expr.sql(dialect=dialect)

    def _build_filter_expressions(
        self,
        *,
        filters: dict[str, Any],
        allowed_columns: list[DatasetColumnRecord],
        dialect: str,
    ) -> list[exp.Expression]:
        if not filters:
            return []

        allowed_names = {column.name.lower() for column in allowed_columns}
        expressions: list[exp.Expression] = []
        for raw_column, raw_value in filters.items():
            column = str(raw_column or "").strip()
            if not column:
                continue
            if allowed_names and column.lower() not in allowed_names:
                continue

            column_expr = exp.Column(this=exp.Identifier(this=column, quoted=True))
            if isinstance(raw_value, dict):
                operator = str(raw_value.get("operator") or "eq").strip().lower()
                value = raw_value.get("value")
                expressions.extend(
                    self._apply_operator_filter(
                        column_expr=column_expr,
                        operator=operator,
                        value=value,
                        dialect=dialect,
                    )
                )
                continue

            if isinstance(raw_value, list):
                literals = [self._literal_expression(item, dialect=dialect) for item in raw_value]
                expressions.append(exp.In(this=column_expr, expressions=literals))
                continue

            expressions.append(exp.EQ(this=column_expr, expression=self._literal_expression(raw_value, dialect=dialect)))

        return expressions

    def _apply_operator_filter(
        self,
        *,
        column_expr: exp.Column,
        operator: str,
        value: Any,
        dialect: str,
    ) -> list[exp.Expression]:
        if operator in {"eq", "equals"}:
            return [exp.EQ(this=column_expr, expression=self._literal_expression(value, dialect=dialect))]
        if operator in {"neq", "not_equals"}:
            return [exp.NEQ(this=column_expr, expression=self._literal_expression(value, dialect=dialect))]
        if operator in {"gt", "greater_than"}:
            return [exp.GT(this=column_expr, expression=self._literal_expression(value, dialect=dialect))]
        if operator in {"gte", "greater_than_or_equal"}:
            return [exp.GTE(this=column_expr, expression=self._literal_expression(value, dialect=dialect))]
        if operator in {"lt", "less_than"}:
            return [exp.LT(this=column_expr, expression=self._literal_expression(value, dialect=dialect))]
        if operator in {"lte", "less_than_or_equal"}:
            return [exp.LTE(this=column_expr, expression=self._literal_expression(value, dialect=dialect))]
        if operator in {"contains", "like"}:
            return [
                exp.Like(
                    this=column_expr,
                    expression=self._literal_expression(f"%{value}%", dialect=dialect),
                )
            ]
        if operator == "in" and isinstance(value, list):
            return [
                exp.In(
                    this=column_expr,
                    expressions=[self._literal_expression(item, dialect=dialect) for item in value],
                )
            ]
        return [exp.EQ(this=column_expr, expression=self._literal_expression(value, dialect=dialect))]

    def _build_row_filter_expressions(
        self,
        *,
        policy: DatasetPolicyRecord,
        request_context: dict[str, Any],
        workspace_id: uuid.UUID,
        project_id: uuid.UUID | None,
        user_id: uuid.UUID,
        dialect: str,
    ) -> list[exp.Expression]:
        templates = list(policy.row_filters_json or [])
        if not templates:
            return []

        render_context: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "project_id": str(project_id) if project_id else None,
            "user_id": str(user_id),
        }
        render_context.update(request_context or {})

        expressions: list[exp.Expression] = []
        for template in templates:
            if not isinstance(template, str) or not template.strip():
                continue
            rendered = render_sql_with_params(template, render_context)
            try:
                expressions.append(sqlglot.parse_one(rendered, read=dialect))
            except sqlglot.ParseError as exc:
                raise BusinessValidationError(f"Invalid row filter policy expression: {exc}") from exc
        return expressions

    def _build_count_sql(
        self,
        *,
        table_key: str,
        filters: list[exp.Expression],
        dialect: str,
    ) -> str:
        query = (
            exp.select(exp.alias_(exp.Count(this=exp.Star()), "row_count", quoted=True))
            .from_(exp.table_(table_key, quoted=False))
        )
        if filters:
            query = query.where(exp.and_(*filters))
        return query.sql(dialect=dialect)

    def _build_column_profile_sql(
        self,
        *,
        table_key: str,
        column_name: str,
        filters: list[exp.Expression],
        dialect: str,
    ) -> str:
        column_expr = exp.Column(this=exp.Identifier(this=column_name, quoted=True))
        distinct_expr = exp.alias_(
            exp.Count(this=column_expr.copy(), distinct=True),
            "distinct_count",
            quoted=True,
        )
        null_expr = exp.alias_(
            exp.Sum(
                this=exp.Case(
                    ifs=[
                        (
                            exp.Is(this=column_expr.copy(), expression=exp.Null()),
                            exp.Literal.number(1),
                        )
                    ],
                    default=exp.Literal.number(0),
                )
            ),
            "null_count",
            quoted=True,
        )
        query = exp.select(distinct_expr, null_expr).from_(exp.table_(table_key, quoted=False))
        if filters:
            query = query.where(exp.and_(*filters))
        return query.sql(dialect=dialect)

    @staticmethod
    def _literal_expression(value: Any, *, dialect: str) -> exp.Expression:
        if value is None:
            return exp.Null()
        if isinstance(value, bool):
            return exp.true() if value else exp.false()
        if isinstance(value, (int, float)):
            return exp.Literal.number(value)
        if isinstance(value, (dict, list)):
            return exp.Literal.string(json.dumps(value))
        return exp.Literal.string(str(value))

    @staticmethod
    def _extract_execution_meta(execution: dict[str, Any]) -> dict[str, int | None]:
        execution_payload = execution.get("execution") if isinstance(execution, dict) else {}
        if not isinstance(execution_payload, dict):
            return {"duration_ms": None, "bytes_scanned": None}
        total_runtime = execution_payload.get("total_runtime_ms")
        duration_ms = int(total_runtime) if isinstance(total_runtime, (int, float)) else None
        bytes_scanned = 0
        has_bytes = False
        for metric in execution_payload.get("stage_metrics") or []:
            if not isinstance(metric, dict):
                continue
            value = metric.get("bytes_written")
            if isinstance(value, (int, float)):
                bytes_scanned += int(value)
                has_bytes = True
        return {
            "duration_ms": duration_ms,
            "bytes_scanned": bytes_scanned if has_bytes else None,
        }

    @staticmethod
    def _extract_single_numeric(
        execution: dict[str, Any],
        *,
        preferred_keys: list[str],
    ) -> int | None:
        rows_payload = execution.get("rows") or []
        if not isinstance(rows_payload, list) or not rows_payload:
            return None
        first_row = rows_payload[0]
        if not isinstance(first_row, dict):
            return None

        lowered = {str(key).lower(): value for key, value in first_row.items()}
        for key in preferred_keys:
            value = lowered.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.strip().isdigit():
                return int(value.strip())

        for value in first_row.values():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.strip().isdigit():
                return int(value.strip())
        return None
