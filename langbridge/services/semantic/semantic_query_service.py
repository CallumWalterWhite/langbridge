import logging
from typing import Any
from uuid import UUID
import uuid
from errors.application_errors import BusinessValidationError
from connectors.config import ConnectorRuntimeType
from connectors.connector import QueryResult, SqlConnector
from models.connectors import ConnectorResponse
from services.connector_service import ConnectorService
from .semantic_model_service import SemanticModelService
from semantic.query import (
    SemanticQuery,
    SemanticQueryEngine,
)
from models.semantic import (
    SemanticQueryRequest,
    SemanticQueryResponse,
    SemanticQueryMetaResponse,
    SemanticModelRecordResponse
)
from semantic.loader import SemanticModelError, load_semantic_model
from semantic.model import SemanticModel

class SemanticQueryService:
    def __init__(self, 
                 semantic_model_service: SemanticModelService,
                 connector_service: ConnectorService
    ):
        self._semantic_model_service = semantic_model_service
        self._connector_service = connector_service
        self._engine = SemanticQueryEngine()
        self._logger = logging.getLogger(__name__)

    async def query_request(
            self,
            semantic_query_request: SemanticQueryRequest
    ) -> SemanticQueryResponse:
        semantic_model_record: SemanticModelRecordResponse = await self._semantic_model_service.get_model(
            model_id=semantic_query_request.semantic_model_id,
            organization_id=semantic_query_request.organization_id
        )

        if semantic_model_record is None:
            raise BusinessValidationError("Semantic model not found")
        
        try:
            semantic_model: SemanticModel = load_semantic_model(semantic_model_record.content_yaml)
        except SemanticModelError as exc:
            raise BusinessValidationError(f"Semantic model failed validation: {exc}") from exc
        semantic_query: SemanticQuery = SemanticQuery.model_validate(semantic_query_request.query)

        self._logger.info(f"Semantic model: {semantic_model}")
        self._logger.info(f"Semantic query: {semantic_query}")

        connector_response: ConnectorResponse = await self._connector_service.get_connector(semantic_model_record.connector_id)

        connector_type: ConnectorRuntimeType = ConnectorRuntimeType(connector_response.connector_type.upper()) # type: ignore

        sql_connector: SqlConnector = await self._connector_service.async_create_sql_connector(
            connector_type, 
            connector_response.config, # type: ignore (not null)
        )

        if not isinstance(sql_connector, SqlConnector):
            raise BusinessValidationError("Only SQL connectors are supported for semantic queries.")

        rewrite_expression = None
        if sql_connector.EXPRESSION_REWRITE:
            rewrite_expression = getattr(sql_connector, "rewrite_expression", None)
            if rewrite_expression is None:
                raise BusinessValidationError(
                    "Semantic query translation failed: connector expression rewriter missing."
                )

        try:
            plan = self._engine.compile(
                semantic_query,
                semantic_model,
                dialect=sql_connector.DIALECT.value.lower(),
                rewrite_expression=rewrite_expression,
            )
        except Exception as exc:
            raise BusinessValidationError(f"Semantic query translation failed: {exc}") from exc

        self._logger.info(f"Translated SQL {plan.sql}")

        result: QueryResult = await sql_connector.execute(plan.sql)

        return SemanticQueryResponse(
            id=uuid.uuid4(),
            organization_id=semantic_query_request.organization_id,
            project_id=semantic_query_request.project_id,
            semantic_model_id=semantic_query_request.semantic_model_id,
            data=self._engine.format_rows(result.columns, result.rows),
            annotations=plan.annotations,
            metadata=plan.metadata,
        )

    async def get_meta(
            self,
            semantic_model_id: UUID,
            organization_id: UUID,
    ) -> SemanticQueryMetaResponse:
        semantic_model_record: SemanticModelRecordResponse = await self._semantic_model_service.get_model(
            model_id=semantic_model_id,
            organization_id=organization_id,
        )

        try:
            semantic_model = load_semantic_model(semantic_model_record.content_yaml)
        except SemanticModelError as exc:
            raise BusinessValidationError(f"Semantic model failed validation: {exc}") from exc

        payload = semantic_model.model_dump(by_alias=True, exclude_none=True)
        self._attach_full_column_paths(payload)
        return SemanticQueryMetaResponse(
            id=semantic_model_id,
            name=semantic_model_record.name,
            description=semantic_model_record.description,
            connector_id=semantic_model_record.connector_id,
            organization_id=semantic_model_record.organization_id,
            project_id=semantic_model_record.project_id,
            semantic_model=payload,
        )

    @staticmethod
    def _attach_full_column_paths(payload: dict[str, Any]) -> None:
        tables = payload.get("tables")
        if not isinstance(tables, dict):
            return
        for table in tables.values():
            if not isinstance(table, dict):
                continue
            schema = str(table.get("schema") or "").strip()
            table_name = str(table.get("name") or "").strip()
            if not table_name:
                continue
            base = f"{schema}.{table_name}" if schema else table_name
            for collection_key in ("dimensions", "measures"):
                items = table.get(collection_key)
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    column_name = str(item.get("name") or "").strip()
                    if not column_name:
                        continue
                    item["full_path"] = f"{base}.{column_name}"

