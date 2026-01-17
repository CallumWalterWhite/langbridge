from uuid import UUID
import sqlglot
import yaml
from errors.application_errors import BusinessValidationError
from connectors.config import ConnectorRuntimeType
from connectors.connector import QueryResult, SqlConnector
from models.connectors import ConnectorResponse
from semantic.query.query_model import SemanticQuery
from services.connector_service import ConnectorService
from .semantic_model_service import SemanticModelService
from semantic.query import (
    TsqlSemanticTranslator,
    SemanticQuery
)
from models.semantic import (
    SemanticQueryRequest,
    SemanticQueryResponse,
    SemanticModelRecordResponse
)
from semantic.model import SemanticModel

class SemanticQueryService:
    def __init__(self, 
                 semantic_model_service: SemanticModelService,
                 connector_service: ConnectorService
    ):
        self._semantic_model_service = semantic_model_service
        self._translator = TsqlSemanticTranslator
        self._connector_service = connector_service

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
        
        parsed_dict = yaml.safe_load(semantic_model_record.content_yaml)
        semantic_model: SemanticModel = SemanticModel.model_validate(parsed_dict)
        semantic_query: SemanticQuery = SemanticQuery.model_validate(semantic_query_request.query)

        try:
            sql = self._translator().translate(semantic_query, semantic_model)
        except Exception as e:
            raise BusinessValidationError(f"Semantic query translation failed: {e}")
        

        connector_response: ConnectorResponse = await self._connector_service.get_connector(semantic_model_record.connector_id)

        connector_type: ConnectorRuntimeType = ConnectorRuntimeType(connector_response.connector_type.upper()) # type: ignore

        sql_connector: SqlConnector = await self._connector_service.async_create_sql_connector(
            connector_type, 
            connector_response.config, # type: ignore (not null)
        )

        dialect_sql: str = self.__transpile(sql, "tsql")

        result: QueryResult = await sql_connector.execute(dialect_sql)

        return SemanticQueryResponse(
            id=UUID(),
            organization_id=semantic_query_request.organization_id,
            project_id=semantic_query_request.project_id,
            semantic_model_id=semantic_query_request.semantic_model_id,
            response=result.sql
        )

    def __transpile(self, sql: str, target_dialect: str) -> str:
        try:
            dialect_sql = sqlglot.transpile(sql, read="tsql", write=target_dialect)[0]
        except Exception as exc:
            raise BusinessValidationError(f"Semantic query translation failed: {exc}")
        return dialect_sql
