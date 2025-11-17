import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import yaml

from connectors.config import ConnectorRuntimeType
from db.auth import Project
from db.semantic import SemanticModelEntry
from errors.application_errors import BusinessValidationError
from errors.connector_errors import ConnectorError
from repositories.organization_repository import (
    OrganizationRepository,
    ProjectRepository,
)
from repositories.semantic_model_repository import SemanticModelRepository
from models.semantic_models import SemanticModelCreateRequest, SemanticModelRecordResponse
from semantic import SemanticModel
from semantic.semantic_model_builder import SemanticModelBuilder
from services.agent_service import AgentService
from services.connector_service import ConnectorService
from utils.embedding_provider import EmbeddingProvider, EmbeddingProviderError

VECTOR_VALUE_LIMIT = 200
VALUE_MAX_LENGTH = 256


class SemanticModelService:
    def __init__(
        self,
        repository: SemanticModelRepository,
        builder: SemanticModelBuilder,
        organization_repository: OrganizationRepository,
        project_repository: ProjectRepository,
        connector_service: ConnectorService,
        agent_service: AgentService,
    ) -> None:
        self._repository = repository
        self._builder = builder
        self._organization_repository = organization_repository
        self._project_repository = project_repository
        self._connector_service = connector_service
        self._agent_service = agent_service

    async def generate_model_yaml(self, connector_id: UUID) -> str:
        return await self._builder.build_yaml_for_scope(connector_id)

    async def list_models(
        self,
        organization_id: UUID,
        project_id: UUID | None = None,
    ) -> list[SemanticModelRecordResponse]:
        models = await self._repository.list_for_scope(
            organization_id=organization_id,
            project_id=project_id,
        )
        return [SemanticModelRecordResponse.model_validate(model) for model in models]

    async def list_all_models(self) -> list[SemanticModelRecordResponse]:
        models = await self._repository.get_all()
        return [SemanticModelRecordResponse.model_validate(model) for model in models]

    async def get_model(
        self,
        model_id: UUID,
        organization_id: UUID,
    ) -> SemanticModelRecordResponse:
        model = await self._get_model_entity(model_id=model_id, organization_id=organization_id)
        return SemanticModelRecordResponse.model_validate(model)

    async def delete_model(self, model_id: UUID, organization_id: UUID) -> None:
        model = await self._get_model_entity(model_id=model_id, organization_id=organization_id)
        await self._repository.delete(model)

    async def create_model(
        self,
        request: SemanticModelCreateRequest,
    ) -> SemanticModelRecordResponse:
        organization = await self._organization_repository.get_by_id(
            request.organization_id
        )
        if not organization:
            raise BusinessValidationError("Organization not found")

        project: Project | None = None
        if request.project_id:
            project: Project | None = await self._project_repository.get_by_id(request.project_id)
            if not project:
                raise BusinessValidationError("Project not found")
            if project.organization_id != organization.id:
                raise BusinessValidationError(
                    "Project does not belong to the specified organization"
                )

        if request.auto_generate or not request.model_yaml:
            semantic_model = await self._builder.build_for_scope(
                connector_id=request.connector_id
            )
            payload = self._builder.build_sql_analyst_payload(semantic_model)
        else:
            try:
                raw = yaml.safe_load(request.model_yaml)
                if not isinstance(raw, dict):
                    raise BusinessValidationError("Semantic model YAML must represent a mapping.")
                if "entities" in raw:
                    payload = raw
                else:
                    semantic_model = SemanticModel.model_validate(raw)
                    payload = self._builder.build_sql_analyst_payload(semantic_model)
            except yaml.YAMLError as exc:
                raise BusinessValidationError(
                    f"Invalid semantic model YAML: {exc}"
                ) from exc
            except ValueError as exc:
                raise BusinessValidationError(
                    f"Semantic model failed validation: {exc}"
                ) from exc

        await self._populate_vector_indexes(payload, request.connector_id)

        model_yaml = yaml.safe_dump(payload, sort_keys=False)
        content_json = json.dumps(payload)

        entry = SemanticModelEntry(
            id=uuid.uuid4(),
            connector_id=request.connector_id,
            organization_id=request.organization_id,
            project_id=request.project_id,
            name=request.name,
            description=request.description,
            content_yaml=model_yaml,
            content_json=content_json,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self._repository.add(entry)
        return SemanticModelRecordResponse.model_validate(entry)

    async def _get_model_entity(self, model_id: UUID, organization_id: UUID) -> SemanticModelEntry:
        model = await self._repository.get_for_scope(
            model_id=model_id,
            organization_id=organization_id,
        )
        if not model:
            raise BusinessValidationError("Semantic model not found")
        return model

    async def _populate_vector_indexes(self, payload: Dict[str, Any], connector_id: UUID) -> None:
        vector_targets = self._discover_vectorized_columns(payload)
        if not vector_targets:
            return

        connector = await self._connector_service.get_connector(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found for vectorization.")

        if not connector.connector_type:
            raise BusinessValidationError("Connector missing runtime type; cannot vectorize semantic model.")
        runtime = ConnectorRuntimeType(connector.connector_type.upper())
        sql_connector = await self._connector_service.async_create_sql_connector(
            runtime,
            connector.config or {},
        )

        embedder = await self._build_embedding_provider()

        for target in vector_targets:
            raw_values = await self._fetch_distinct_values(
                sql_connector,
                target["schema"],
                target["table"],
                target["column"],
            )
            values = self._prepare_vector_values(raw_values)
            if not values:
                target["meta"].pop("vector_index", None)
                continue

            embeddings = await embedder.embed(values)
            vector_entries = [
                {"value": value, "embedding": vector}
                for value, vector in zip(values, embeddings, strict=False)
            ]
            if not vector_entries:
                target["meta"].pop("vector_index", None)
                continue

            target["meta"]["vector_index"] = {
                "model": embedder.embedding_model,
                "values": vector_entries,
            }

    def _discover_vectorized_columns(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        entities = payload.get("entities") or {}
        targets: List[Dict[str, Any]] = []
        for entity_name, entity_meta in entities.items():
            columns = (entity_meta or {}).get("columns") or {}
            if not columns:
                continue
            schema = entity_meta.get("schema")
            table_name = entity_meta.get("name") or entity_meta.get("table")
            if not table_name:
                continue
            if not schema and isinstance(table_name, str) and "." in table_name:
                schema, table_name = table_name.split(".", 1)
            for column_name, column_meta in columns.items():
                if not isinstance(column_meta, dict) or not column_meta.get("vectorized"):
                    continue
                column_meta.pop("vector_index", None)
                targets.append(
                    {
                        "entity": entity_name,
                        "schema": schema,
                        "table": table_name,
                        "column": column_name,
                        "meta": column_meta,
                    }
                )
        return targets

    async def _build_embedding_provider(self) -> EmbeddingProvider:
        connections = await self._agent_service.list_llm_connection_secrets()
        if not connections:
            raise BusinessValidationError(
                "No LLM connections configured; enable one before vectorizing semantic models."
            )
        connection = connections[0]
        try:
            return EmbeddingProvider.from_llm_connection(connection)
        except EmbeddingProviderError as exc:
            raise BusinessValidationError(f"Embedding provider misconfigured: {exc}") from exc

    async def _fetch_distinct_values(
        self,
        sql_connector,
        schema: Optional[str],
        table_name: str,
        column_name: str,
    ) -> List[Any]:
        attempts = self._build_identifier_attempts(schema, table_name, column_name)
        last_error: Exception | None = None
        for attempt in attempts:
            query = (
                f"SELECT DISTINCT {attempt['column']} "
                f"FROM {attempt['table']} "
                f"WHERE {attempt['column']} IS NOT NULL "
                f"LIMIT {VECTOR_VALUE_LIMIT}"
            )
            try:
                result = await sql_connector.execute(query, max_rows=VECTOR_VALUE_LIMIT)
            except (ConnectorError, Exception) as exc:  # pragma: no cover - depends on connector runtime
                last_error = exc
                continue
            return [row[0] for row in result.rows if row]

        if last_error:
            raise BusinessValidationError(
                f"Unable to fetch values for {table_name}.{column_name}: {last_error}"
            ) from last_error
        return []

    def _build_identifier_attempts(
        self,
        schema: Optional[str],
        table_name: str,
        column_name: str,
    ) -> List[Dict[str, str]]:
        attempts = []
        for left, right in (('"', '"'), ("`", "`"), ("[", "]"), (None, None)):
            column_expr = self._format_identifier(column_name, left, right)
            if schema:
                table_expr = (
                    f"{self._format_identifier(schema, left, right)}."
                    f"{self._format_identifier(table_name, left, right)}"
                )
            else:
                table_expr = self._format_identifier(table_name, left, right)
            attempts.append({"table": table_expr, "column": column_expr})
        return attempts

    @staticmethod
    def _format_identifier(value: str, left: Optional[str], right: Optional[str]) -> str:
        if not left and not right:
            return value
        left_token = left or ""
        right_token = right or ""
        escaped = value
        if right_token:
            escaped = escaped.replace(right_token, right_token * 2)
        elif left_token:
            escaped = escaped.replace(left_token, left_token * 2)
        return f"{left_token}{escaped}{right_token}"

    def _prepare_vector_values(self, values: List[Any]) -> List[str]:
        deduped: List[str] = []
        seen: set[str] = set()
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            if len(text) > VALUE_MAX_LENGTH:
                text = text[:VALUE_MAX_LENGTH]
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(text)
            if len(deduped) >= VECTOR_VALUE_LIMIT:
                break
        return deduped
