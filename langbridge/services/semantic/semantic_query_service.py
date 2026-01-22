import logging
from typing import Any, Dict, List
from uuid import UUID
import uuid
import sqlglot
import sqlglot.expressions as exp
from errors.application_errors import BusinessValidationError
from connectors.config import ConnectorRuntimeType
from connectors.connector import QueryResult, SqlConnector
from models.connectors import ConnectorResponse
from services.connector_service import ConnectorService
from .semantic_model_service import SemanticModelService
from semantic.query import (
    TsqlSemanticTranslator,
    SemanticQuery
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
        self._translator = TsqlSemanticTranslator
        self._connector_service = connector_service
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

        try:
            tree: exp.Select = self._translator().translate(
                semantic_query,
                semantic_model,
                dialect=sql_connector.DIALECT.value.lower(),
            )
        except Exception as e:
            raise BusinessValidationError(f"Semantic query translation failed: {e}")
        
        dialect_sql: str = self.__transpile(tree, sql_connector)

        self._logger.info(f"Translated SQL {dialect_sql}")

        result: QueryResult = await sql_connector.execute(dialect_sql)

        return SemanticQueryResponse(
            id=uuid.uuid4(),
            organization_id=semantic_query_request.organization_id,
            project_id=semantic_query_request.project_id,
            semantic_model_id=semantic_query_request.semantic_model_id,
            data=self.__format_data_response(result),
            annotations=self.__format_annotations_response(semantic_query, semantic_model)
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
        return SemanticQueryMetaResponse(
            id=semantic_model_id,
            name=semantic_model_record.name,
            description=semantic_model_record.description,
            connector_id=semantic_model_record.connector_id,
            organization_id=semantic_model_record.organization_id,
            project_id=semantic_model_record.project_id,
            semantic_model=payload,
        )

    def __transpile(self, tree: exp.Select, target_connector: SqlConnector) -> str:
        if not isinstance(target_connector, SqlConnector):
            raise BusinessValidationError("Only SQL connectors are supported for semantic queries.")
        
        if target_connector.EXPRESSION_REWRITE:
            try:
                rewritten_expression: sqlglot.Expression = tree.transform(
                    lambda node: target_connector.rewrite_expression(node)  # type: ignore
                )
                self._logger.debug(f"Rewritten expression: {rewritten_expression}")
                dialect_sql = rewritten_expression.sql(dialect=target_connector.DIALECT.value.lower())
            except Exception as exc:
                raise BusinessValidationError(f"Semantic query translation failed: {exc}") from exc
            return dialect_sql
        else:
            return tree.sql(dialect=target_connector.DIALECT.value.lower())

    def __format_data_response(
            self,
            result: QueryResult
    ) -> List[Dict[str, Any]]:
        return [dict(zip(result.columns, row)) for row in result.rows]
    
    def __format_annotations_response(
            self,
            semantic_query: SemanticQuery,
            semantic_model: SemanticModel) -> List[Dict[str, str]]:
        annoinations: List[Dict[str, Any]] = []
        for table in semantic_model.tables.values():
            for annotation in table.get_annotations().items():
                annoinations.append({
                    "column": annotation[0],
                    "name": annotation[1]
                })
        return annoinations
