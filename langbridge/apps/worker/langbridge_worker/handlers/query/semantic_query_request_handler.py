import json
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from langbridge.apps.worker.langbridge_worker.handlers.jobs.job_event_emitter import (
    BrokerJobEventEmitter,
)
from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.common.langbridge_common.contracts.connectors import ConnectorResponse
from langbridge.packages.common.langbridge_common.contracts.jobs.semantic_query_job import (
    CreateSemanticQueryJobRequest,
)
from langbridge.packages.common.langbridge_common.contracts.semantic import (
    SemanticQueryResponse,
    UnifiedSemanticQueryResponse,
)
from langbridge.packages.common.langbridge_common.db.job import JobRecord, JobStatus
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
)
from langbridge.packages.common.langbridge_common.interfaces.agent_events import (
    AgentEventVisibility,
)
from langbridge.packages.common.langbridge_common.repositories.connector_repository import (
    ConnectorRepository,
)
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.common.langbridge_common.repositories.semantic_model_repository import (
    SemanticModelRepository,
)
from langbridge.packages.connectors.langbridge_connectors.api import (
    ConnectorRuntimeTypeSqlDialectMap,
    SqlConnector,
    SqlConnectorFactory,
    get_connector_config_factory,
)
from langbridge.packages.connectors.langbridge_connectors.api.config import ConnectorRuntimeType
from langbridge.packages.connectors.langbridge_connectors.api._trino.connector import (
    TrinoConnector,
    TrinoConnectorConfig,
)
from langbridge.packages.messaging.langbridge_messaging.broker.base import MessageBroker
from langbridge.packages.messaging.langbridge_messaging.contracts.base import MessageType
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.semantic_query import (
    SemanticQueryRequestMessage,
)
from langbridge.packages.messaging.langbridge_messaging.handler import BaseMessageHandler
from langbridge.packages.semantic.langbridge_semantic.loader import (
    SemanticModelError,
    load_semantic_model,
)
from langbridge.packages.semantic.langbridge_semantic.model import SemanticModel
from langbridge.packages.semantic.langbridge_semantic.query import SemanticQuery, SemanticQueryEngine
from langbridge.packages.semantic.langbridge_semantic.unified_query import (
    TenantAwareQueryContext,
    UnifiedSourceModel,
    apply_tenant_aware_context,
    build_unified_semantic_model,
)


class SemanticQueryRequestHandler(BaseMessageHandler):
    message_type: MessageType = MessageType.SEMANTIC_QUERY_REQUEST

    def __init__(
        self,
        job_repository: JobRepository,
        semantic_model_repository: SemanticModelRepository,
        connector_repository: ConnectorRepository,
        message_broker: MessageBroker,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._job_repository = job_repository
        self._semantic_model_repository = semantic_model_repository
        self._connector_repository = connector_repository
        self._message_broker = message_broker
        self._engine = SemanticQueryEngine()
        self._sql_connector_factory = SqlConnectorFactory()

    async def handle(self, payload: SemanticQueryRequestMessage) -> None:
        self._logger.info("Received semantic query job request %s", payload.job_id)
        job_record = await self._job_repository.get_by_id(payload.job_id)
        if job_record is None:
            raise BusinessValidationError(f"Job with ID {payload.job_id} does not exist.")

        if job_record.status in {
            JobStatus.succeeded,
            JobStatus.failed,
            JobStatus.cancelled,
        }:
            self._logger.info(
                "Job %s already in terminal state %s; skipping.",
                job_record.id,
                job_record.status,
            )
            return None

        event_emitter = BrokerJobEventEmitter(
            job_record=job_record,
            broker_client=self._message_broker,
            logger=self._logger,
        )
        job_record.status = JobStatus.running
        job_record.progress = 5
        job_record.status_message = "Semantic query started."
        if job_record.started_at is None:
            job_record.started_at = datetime.now(timezone.utc)
        await event_emitter.emit(
            event_type="SemanticQueryStarted",
            message="Semantic query started.",
            visibility=AgentEventVisibility.public,
            source="worker",
            details={"job_id": str(job_record.id)},
        )

        try:
            request = self._parse_job_payload(job_record)
            semantic_response = await self._run_query(job_record, request, event_emitter)

            row_count = len(semantic_response.data)
            job_record.result = {
                "result": semantic_response.model_dump(mode="json"),
                "summary": f"Semantic query completed with {row_count} rows.",
            }
            job_record.status = JobStatus.succeeded
            job_record.progress = 100
            job_record.status_message = "Semantic query completed."
            job_record.finished_at = datetime.now(timezone.utc)
            job_record.error = None
            await event_emitter.emit(
                event_type="SemanticQueryCompleted",
                message="Semantic query completed.",
                visibility=AgentEventVisibility.public,
                source="worker",
                details={"job_id": str(job_record.id), "row_count": row_count},
            )
        except Exception as exc:  # pragma: no cover - defensive background worker guard
            self._logger.exception("Semantic query job %s failed: %s", job_record.id, exc)
            job_record.status = JobStatus.failed
            job_record.finished_at = datetime.now(timezone.utc)
            job_record.status_message = "Semantic query failed."
            job_record.error = {"message": str(exc)}
            await event_emitter.emit(
                event_type="SemanticQueryFailed",
                message="Semantic query failed.",
                visibility=AgentEventVisibility.public,
                source="worker",
                details={"job_id": str(job_record.id), "error": str(exc)},
            )

        return None

    def _parse_job_payload(self, job_record: JobRecord) -> CreateSemanticQueryJobRequest:
        raw_payload = job_record.payload
        if isinstance(raw_payload, str):
            try:
                payload_data = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                raise BusinessValidationError(
                    f"Job payload for {job_record.id} is not valid JSON."
                ) from exc
        elif isinstance(raw_payload, dict):
            payload_data = raw_payload
        else:
            raise BusinessValidationError(
                f"Job payload for {job_record.id} must be an object or JSON string."
            )

        try:
            return CreateSemanticQueryJobRequest.model_validate(payload_data)
        except ValidationError as exc:
            raise BusinessValidationError(
                f"Job payload for {job_record.id} is invalid for semantic query execution."
            ) from exc

    async def _run_query(
        self,
        job_record: JobRecord,
        request: CreateSemanticQueryJobRequest,
        event_emitter: BrokerJobEventEmitter,
    ) -> SemanticQueryResponse | UnifiedSemanticQueryResponse:
        job_record.progress = 20
        job_record.status_message = "Loading semantic model."
        await event_emitter.emit(
            event_type="SemanticQueryLoadingModel",
            message="Loading semantic model.",
            visibility=AgentEventVisibility.public,
            source="worker",
            details={"query_scope": request.query_scope},
        )

        semantic_query = self._load_query_payload(request.query)
        semantic_model: SemanticModel
        table_connector_map: dict[str, uuid.UUID] | None = None
        execution_connector_id: uuid.UUID
        sql_connector: Any
        semantic_model_id: uuid.UUID | None = None

        if request.query_scope == "unified":
            if not request.semantic_model_ids:
                raise BusinessValidationError(
                    "semantic_model_ids must include at least one model id for unified query scope."
                )
            semantic_model, table_connector_map = await self._build_unified_model_and_map(
                organization_id=request.organisation_id,
                semantic_model_ids=request.semantic_model_ids,
                joins=request.joins,
                metrics=request.metrics,
            )
            execution_connector_id, sql_connector = await self._create_unified_trino_connector(
                organization_id=request.organisation_id,
            )
        else:
            if request.semantic_model_id is None:
                raise BusinessValidationError(
                    "semantic_model_id is required for semantic_model query scope."
                )
            semantic_model_record = await self._semantic_model_repository.get_for_scope(
                model_id=request.semantic_model_id,
                organization_id=request.organisation_id,
            )
            if semantic_model_record is None:
                raise BusinessValidationError("Semantic model not found.")
            semantic_model = self._load_model_payload(semantic_model_record.content_yaml)
            execution_connector_id = semantic_model_record.connector_id
            semantic_model_id = request.semantic_model_id
            connector = await self._connector_repository.get_by_id(execution_connector_id)
            if connector is None:
                raise BusinessValidationError("Connector not found for semantic query.")
            connector_response = ConnectorResponse.from_connector(
                connector,
                organization_id=request.organisation_id,
                project_id=request.project_id,
            )
            if connector_response.connector_type is None:
                raise BusinessValidationError("Connector type is required for semantic query execution.")

            connector_type = ConnectorRuntimeType(connector_response.connector_type.upper())
            sql_connector = await self._create_sql_connector(
                connector_type=connector_type,
                connector_config=connector_response.config or {},
            )
            if not isinstance(sql_connector, SqlConnector):
                raise BusinessValidationError("Only SQL connectors are supported for semantic queries.")

        execution_model = semantic_model
        if request.query_scope == "unified":
            execution_model = apply_tenant_aware_context(
                semantic_model,
                context=TenantAwareQueryContext(
                    organization_id=request.organisation_id,
                    execution_connector_id=execution_connector_id,
                ),
                table_connector_map=table_connector_map,
            )

        job_record.progress = 45
        job_record.status_message = "Compiling semantic query."
        await event_emitter.emit(
            event_type="SemanticQueryCompiling",
            message="Compiling semantic query.",
            visibility=AgentEventVisibility.public,
            source="worker",
        )

        rewrite_expression = None
        if getattr(sql_connector, "EXPRESSION_REWRITE", False):
            rewrite_expression = getattr(sql_connector, "rewrite_expression", None)
            if rewrite_expression is None:
                raise BusinessValidationError(
                    "Semantic query translation failed: connector expression rewriter missing."
                )

        try:
            plan = self._engine.compile(
                semantic_query,
                execution_model,
                dialect=sql_connector.DIALECT.value.lower(),
                rewrite_expression=rewrite_expression,
            )
        except Exception as exc:
            raise BusinessValidationError(f"Semantic query translation failed: {exc}") from exc

        job_record.progress = 70
        job_record.status_message = "Executing SQL."
        await event_emitter.emit(
            event_type="SemanticQueryExecuting",
            message="Executing semantic query SQL.",
            visibility=AgentEventVisibility.public,
            source="worker",
            details={"sql": plan.sql, "query_scope": request.query_scope},
        )

        query_result = await sql_connector.execute(plan.sql)
        data = self._engine.format_rows(query_result.columns, query_result.rows)

        if request.query_scope == "unified":
            return UnifiedSemanticQueryResponse(
                id=uuid.uuid4(),
                organization_id=request.organisation_id,
                project_id=request.project_id,
                connector_id=execution_connector_id,
                semantic_model_ids=request.semantic_model_ids or [],
                data=data,
                annotations=plan.annotations,
                metadata=plan.metadata,
            )

        if semantic_model_id is None:
            raise BusinessValidationError("semantic_model_id is required for semantic model query scope.")
        return SemanticQueryResponse(
            id=uuid.uuid4(),
            organization_id=request.organisation_id,
            project_id=request.project_id,
            semantic_model_id=semantic_model_id,
            data=data,
            annotations=plan.annotations,
            metadata=plan.metadata,
        )

    async def _build_unified_model_and_map(
        self,
        *,
        organization_id: uuid.UUID,
        semantic_model_ids: list[uuid.UUID],
        joins: list[Any] | None,
        metrics: Mapping[str, Any] | None,
    ) -> tuple[SemanticModel, dict[str, uuid.UUID]]:
        normalized_model_ids = self._normalize_model_ids(semantic_model_ids)
        source_models: list[UnifiedSourceModel] = []
        for semantic_model_id in normalized_model_ids:
            semantic_model_record = await self._semantic_model_repository.get_for_scope(
                model_id=semantic_model_id,
                organization_id=organization_id,
            )
            if semantic_model_record is None:
                raise BusinessValidationError(
                    f"Semantic model '{semantic_model_id}' not found for unified query."
                )
            source_models.append(
                UnifiedSourceModel(
                    model=self._load_model_payload(semantic_model_record.content_yaml),
                    connector_id=semantic_model_record.connector_id,
                )
            )

        joins_payload = [
            join.model_dump(by_alias=True, exclude_none=True)
            if hasattr(join, "model_dump")
            else dict(join)
            for join in (joins or [])
        ]
        metrics_payload: dict[str, Any] = {}
        for metric_name, metric_value in (metrics or {}).items():
            if hasattr(metric_value, "model_dump"):
                metrics_payload[metric_name] = metric_value.model_dump(
                    by_alias=True, exclude_none=True
                )
            elif isinstance(metric_value, Mapping):
                metrics_payload[metric_name] = dict(metric_value)
            else:
                metrics_payload[metric_name] = metric_value

        try:
            return build_unified_semantic_model(
                source_models=source_models,
                joins=joins_payload,
                metrics=metrics_payload or None,
            )
        except (SemanticModelError, ValueError) as exc:
            raise BusinessValidationError(
                f"Unified semantic model failed validation: {exc}"
            ) from exc

    async def _create_unified_trino_connector(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> tuple[uuid.UUID, TrinoConnector]:
        host = settings.UNIFIED_TRINO_HOST.strip()
        if not host:
            raise BusinessValidationError(
                "UNIFIED_TRINO_HOST must be configured for unified semantic query execution."
            )

        connector = TrinoConnector(
            TrinoConnectorConfig(
                host=host,
                port=settings.UNIFIED_TRINO_PORT,
                user=settings.UNIFIED_TRINO_USER,
                password=settings.UNIFIED_TRINO_PASSWORD,
                catalog=settings.UNIFIED_TRINO_CATALOG,
                schema=settings.UNIFIED_TRINO_SCHEMA,
                http_scheme=settings.UNIFIED_TRINO_HTTP_SCHEME,
                verify=settings.UNIFIED_TRINO_VERIFY,
                tenant=str(organization_id),
                source=settings.UNIFIED_TRINO_SOURCE,
            )
        )
        await connector.test_connection()
        return self._build_unified_execution_connector_id(organization_id=organization_id), connector

    @staticmethod
    def _build_unified_execution_connector_id(*, organization_id: uuid.UUID) -> uuid.UUID:
        return uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"langbridge-unified-trino:{organization_id}",
        )

    async def _create_sql_connector(
        self,
        *,
        connector_type: ConnectorRuntimeType,
        connector_config: dict[str, Any],
    ) -> SqlConnector:
        dialect = ConnectorRuntimeTypeSqlDialectMap.get(connector_type)
        if dialect is None:
            raise BusinessValidationError(
                f"Connector type {connector_type.value} does not support SQL operations."
            )
        config_factory = get_connector_config_factory(connector_type)
        config_instance = config_factory.create(connector_config.get("config", {}))
        sql_connector = self._sql_connector_factory.create_sql_connector(
            dialect,
            config_instance,
            logger=self._logger,
        )
        await sql_connector.test_connection()
        return sql_connector

    @staticmethod
    def _load_model_payload(content_yaml: str) -> SemanticModel:
        try:
            return load_semantic_model(content_yaml)
        except SemanticModelError as exc:
            raise BusinessValidationError(
                f"Semantic model failed validation: {exc}"
            ) from exc

    @staticmethod
    def _load_query_payload(query_payload: Mapping[str, Any] | dict[str, Any]) -> SemanticQuery:
        try:
            return SemanticQuery.model_validate(query_payload)
        except Exception as exc:
            raise BusinessValidationError(
                f"Semantic query payload failed validation: {exc}"
            ) from exc

    @staticmethod
    def _normalize_model_ids(semantic_model_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        ordered_unique: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()
        for model_id in semantic_model_ids:
            if model_id in seen:
                continue
            seen.add(model_id)
            ordered_unique.append(model_id)
        if not ordered_unique:
            raise BusinessValidationError(
                "semantic_model_ids must include at least one model id."
            )
        return ordered_unique
