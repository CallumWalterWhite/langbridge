import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Type
from uuid import UUID

import yaml

from langbridge.packages.connectors.langbridge_connectors.api import (
    ConnectorRuntimeType, 
    VectorDBConnectorFactory, 
    VectorDBType, 
    ManagedVectorDB
)
from langbridge.packages.common.langbridge_common.db.auth import Project
from langbridge.packages.common.langbridge_common.db.semantic import SemanticModelEntry
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.common.langbridge_common.errors.connector_errors import ConnectorError
from langbridge.packages.common.langbridge_common.contracts.connectors import ConnectorResponse
from langbridge.apps.api.langbridge_api.services.environment_service import EnvironmentService, EnvironmentSettingKey
from .semantic_search_sercice import SemanticSearchService
from langbridge.packages.common.langbridge_common.repositories.organization_repository import (
    OrganizationRepository,
    ProjectRepository,
)
from langbridge.packages.common.langbridge_common.repositories.semantic_model_repository import SemanticModelRepository
from langbridge.packages.common.langbridge_common.contracts.semantic import (
    SemanticModelRecordResponse,
    SemanticModelCreateRequest,
    SemanticModelUpdateRequest,
)
from langbridge.packages.semantic.langbridge_semantic.loader import SemanticModelError, load_semantic_model
from langbridge.packages.semantic.langbridge_semantic.model import SemanticModel
from langbridge.packages.semantic.langbridge_semantic.semantic_model_builder import SemanticModelBuilder
from langbridge.apps.api.langbridge_api.services.agent_service import AgentService
from langbridge.apps.api.langbridge_api.services.connector_service import ConnectorService
from langbridge.packages.common.langbridge_common.utils.embedding_provider import EmbeddingProvider, EmbeddingProviderError

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
        semantic_search_service: SemanticSearchService,
        emvironment_service: EnvironmentService
    ) -> None:
        self._repository = repository
        self._builder = builder
        self._organization_repository = organization_repository
        self._project_repository = project_repository
        self._connector_service = connector_service
        self._agent_service = agent_service
        self._semantic_search_service = semantic_search_service
        self._emvironment_service = emvironment_service
        
        self._vector_factory = VectorDBConnectorFactory()

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
        return [self._normalize_record(model) for model in models]

    async def list_all_models(self) -> list[SemanticModelRecordResponse]:
        models = await self._repository.get_all()
        return [self._normalize_record(model) for model in models]

    async def get_model(
        self,
        model_id: UUID,
        organization_id: UUID,
    ) -> SemanticModelRecordResponse:
        model = await self._get_model_entity(model_id=model_id, organization_id=organization_id)
        return self._normalize_record(model)

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
        else:
            try:
                semantic_model = load_semantic_model(request.model_yaml)
            except SemanticModelError as exc:
                raise BusinessValidationError(
                    f"Semantic model failed validation: {exc}"
                ) from exc

        connector = await self._connector_service.get_connector(request.connector_id)
        if connector and not semantic_model.connector:
            semantic_model.connector = connector.name if isinstance(connector.name, str) else connector.name.value

        if request.name and not semantic_model.name:
            semantic_model.name = request.name
        if request.description:
            semantic_model.description = request.description

        semantic_id: UUID = uuid.uuid4()

        await self._populate_vector_indexes(semantic_model, request.connector_id, semantic_id)

        payload = semantic_model.model_dump(by_alias=True, exclude_none=True)
        model_yaml = yaml.safe_dump(payload, sort_keys=False)
        content_json = json.dumps(payload)

        entry = SemanticModelEntry(
            id=semantic_id,
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

    async def update_model(
        self,
        model_id: UUID,
        organization_id: UUID,
        request: SemanticModelUpdateRequest,
    ) -> SemanticModelRecordResponse:
        model = await self._get_model_entity(model_id=model_id, organization_id=organization_id)
        organization = await self._organization_repository.get_by_id(organization_id)
        if not organization:
            raise BusinessValidationError("Organization not found")

        project_id = model.project_id
        if "project_id" in request.model_fields_set:
            project_id = request.project_id
        if project_id:
            project = await self._project_repository.get_by_id(project_id)
            if not project:
                raise BusinessValidationError("Project not found")
            if project.organization_id != organization.id:
                raise BusinessValidationError(
                    "Project does not belong to the specified organization"
                )

        connector_id = request.connector_id or model.connector_id

        if request.name is not None and not request.name.strip():
            raise BusinessValidationError("Semantic model name is required")

        rebuild_content = bool(request.auto_generate or request.model_yaml is not None)
        if rebuild_content:
            if request.auto_generate or not request.model_yaml:
                semantic_model = await self._builder.build_for_scope(
                    connector_id=connector_id
                )
            else:
                try:
                    semantic_model = load_semantic_model(request.model_yaml)
                except SemanticModelError as exc:
                    raise BusinessValidationError(
                        f"Semantic model failed validation: {exc}"
                    ) from exc
        else:
            try:
                semantic_model = load_semantic_model(model.content_yaml)
            except SemanticModelError as exc:
                raise BusinessValidationError(
                    f"Semantic model failed validation: {exc}"
                ) from exc

        connector = await self._connector_service.get_connector(connector_id)
        if connector and (request.connector_id is not None or not semantic_model.connector):
            semantic_model.connector = connector.name if isinstance(connector.name, str) else connector.name.value

        if request.name is not None:
            model.name = request.name.strip()
            if model.name and not semantic_model.name:
                semantic_model.name = model.name
        if request.description is not None:
            model.description = request.description.strip() or None
            if model.description and not semantic_model.description:
                semantic_model.description = model.description

        model.connector_id = connector_id
        model.project_id = project_id

        if rebuild_content:
            await self._populate_vector_indexes(
                semantic_model,
                connector_id,
                model.id,
                reset_index=True,
            )

        payload = semantic_model.model_dump(by_alias=True, exclude_none=True)
        model.content_yaml = yaml.safe_dump(payload, sort_keys=False)
        model.content_json = json.dumps(payload)
        model.updated_at = datetime.now(timezone.utc)

        return SemanticModelRecordResponse.model_validate(model)

    async def _get_model_entity(self, model_id: UUID, organization_id: UUID) -> SemanticModelEntry:
        model = await self._repository.get_for_scope(
            model_id=model_id,
            organization_id=organization_id,
        )
        if not model:
            raise BusinessValidationError("Semantic model not found")
        return model

    def _normalize_record(self, model: SemanticModelEntry) -> SemanticModelRecordResponse:
        response = SemanticModelRecordResponse.model_validate(model)
        try:
            semantic_model = load_semantic_model(response.content_yaml)
        except SemanticModelError:
            return response
        if response.name and not semantic_model.name:
            semantic_model.name = response.name
        if response.description and not semantic_model.description:
            semantic_model.description = response.description
        response.content_yaml = semantic_model.yml_dump()
        return response

    async def _populate_vector_indexes(
        self,
        semantic_model: SemanticModel,
        connector_id: UUID,
        semantic_id: UUID,
        reset_index: bool = False,
    ) -> None:
        vector_targets = self._discover_vectorized_dimensions(semantic_model)
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

        vector_db_types: List[VectorDBType] = self._vector_factory.get_all_managed_vector_dbs()
        if not vector_db_types:
            raise BusinessValidationError(
                "No managed vector databases are configured; cannot vectorize semantic model."
            )

        vector_managed_instance, connector_response = await self.__get_default_semantic_vecotr_connnector(connector.organization_id, semantic_id)
        await vector_managed_instance.test_connection()
        if reset_index:
            # Ensure the managed index can be recreated when updating an existing model.
            try:
                await vector_managed_instance.delete_index()
            except Exception as exc:
                message = str(exc).lower()
                if "not found" not in message and "does not exist" not in message:
                    raise

        index_initialized = False
        index_dimension: Optional[int] = None

        for target in vector_targets:
            raw_values = await self._fetch_distinct_values(
                sql_connector,
                target["schema"],
                target["table"],
                target["column"],
            )
            values = self._prepare_vector_values(raw_values)
            if not values:
                target["dimension"].vector_index = None
                continue

            embeddings = await embedder.embed(values)
            if not embeddings:
                target["dimension"].vector_index = None
                continue

            vector_length = len(embeddings[0])
            if not index_initialized:
                await vector_managed_instance.create_index(dimension=vector_length)
                index_initialized = True
                index_dimension = vector_length
            elif index_dimension and vector_length != index_dimension:
                raise BusinessValidationError(
                    "Embedding dimension mismatch while populating vector index."
                )

            metadata_entries = [
                {
                    "entity": target["entity"],
                    "column": target["column"],
                    "value": value,
                }
                for value in values
            ]

            try:
                await vector_managed_instance.upsert_vectors(
                    embeddings,
                    metadata=metadata_entries,
                )
            except ConnectorError as exc:
                raise BusinessValidationError(
                    f"Failed to persist vectors for {target['entity']}.{target['column']}: {exc}"
                ) from exc

            vector_reference = self._build_vector_reference(
                vector_db_type=vector_managed_instance.VECTOR_DB_TYPE,
                connector_id=connector_id,
                entity=target["entity"],
                column=target["column"],
                vector_db_config=getattr(vector_managed_instance, "config", None),
            )

            vector_index_meta: Dict[str, Any] = {
                "model": embedder.embedding_model,
                "dimension": vector_length,
                "size": len(values),
                "vector_namespace": str(connector_response.id),
            }
            # Persist the backing vector store metadata so the orchestrator can evolve to read from it.
            vector_index_meta["vector_store"] = {
                "type": vector_managed_instance.VECTOR_DB_TYPE.value,
            }
            config_dict = getattr(vector_managed_instance, "config", None)
            location = getattr(config_dict, "location", None)
            if location:
                vector_index_meta["vector_store"]["location"] = location
            vector_index_meta["reference"] = {
                "entity": target["entity"],
                "column": target["column"],
                "vector_reference": vector_reference,
            }

            target["dimension"].vector_index = vector_index_meta
            target["dimension"].vector_reference = vector_reference

    async def __get_default_semantic_vecotr_connnector(
            self,
            organization_id: UUID,
            semantic_id: UUID
    ) -> Tuple[ManagedVectorDB, ConnectorResponse]:
        #TODO: revist this, currently only supports FAISS, will break on qdrant managed vector db

        default_vector_connector_id: str | None = await self._emvironment_service.get_setting(
            organization_id=organization_id,
            key=EnvironmentSettingKey.DEFAULT_SEMANTIC_VECTOR_CONNECTOR.value,
        )
        if not default_vector_connector_id:
            raise BusinessValidationError(
                "Default semantic vector connector not configured"
            )

        connector_response: ConnectorResponse = await self._connector_service.get_connector(UUID(default_vector_connector_id))

        vector_managed_class_ref: Type[ManagedVectorDB] = (
            self._vector_factory.get_managed_vector_db_class_reference(VectorDBType(connector_response.connector_type))    
        )
        vector_id: str = f"semantic_model_{connector_response.id.hex}_{semantic_id.hex}_idx" # type: ignore
        vector_managed_instance: ManagedVectorDB = await vector_managed_class_ref.create_managed_instance(
            kwargs={
                "index_name": vector_id
            },
        )

        return vector_managed_instance, connector_response

    def _discover_vectorized_dimensions(self, semantic_model: SemanticModel) -> List[Dict[str, Any]]:
        targets: List[Dict[str, Any]] = []
        for entity_name, table in semantic_model.tables.items():
            schema = table.schema or None
            table_name = table.name
            for dimension in table.dimensions or []:
                if not dimension.vectorized:
                    continue
                targets.append(
                    {
                        "entity": entity_name,
                        "schema": schema,
                        "table": table_name,
                        "column": dimension.name,
                        "dimension": dimension,
                    }
                )
        return targets

    def _build_vector_reference(
        self,
        *,
        vector_db_type: VectorDBType,
        connector_id: UUID,
        entity: str,
        column: str,
        vector_db_config: Any | None,
    ) -> str:
        """
        Build a stable reference string pointing to the managed vector index for a given entity/column pair.
        """
        location = getattr(vector_db_config, "location", None)
        location_token = str(location).strip() if location else "managed"
        entity_component = entity.replace(" ", "_")
        column_component = column.replace(" ", "_")
        return f"{vector_db_type.value}:{location_token}:{connector_id}:{entity_component}.{column_component}"

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
            )
            try:
                result = await sql_connector.execute(query)
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
        return deduped
