

from dataclasses import dataclass
import logging
import re
import yaml
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from connectors import (
    ConnectorRuntimeType,
    TableMetadata,
    ColumnMetadata,
    ForeignKeyMetadata,
    SqlConnector,
)
from orchestrator.tools.sql_analyst.interfaces import QueryResult
from semantic.model import MeasureAggregation
from semantic import Dimension, Measure, Relationship, SemanticModel, Table
from services.connector_service import ConnectorService
from models.connectors import ConnectorResponse

logger = logging.getLogger(__name__)


TYPE_NUMERIC = {"number", "decimal", "numeric", "int", "integer", "float", "double", "real"}
TYPE_BOOLEAN = {"boolean", "bool"}
TYPE_DATE = {"date", "datetime", "timestamp", "time"}

@dataclass
class ScopedTableMetadata:
    schema: str
    table_metadata: TableMetadata
    columns: List[ColumnMetadata]
    foreign_keys: List[ForeignKeyMetadata]

class SemanticModelBuilder:
    """Builds a semantic data model across organization/project connectors."""

    def __init__(
        self,
        connector_service: ConnectorService,
    ) -> None:
        self._connector_service = connector_service
        self._logger = logging.getLogger(__name__)

    async def build_for_scope(
        self,
        connector_id: UUID,
        scope_schemas: Optional[List[str]] = None, # schema scope
        scope_tables: Optional[List[Tuple[str, str]]] = None, # schema, table scope
        scope_columns: Optional[List[Tuple[str, str, str]]] = None, # schema, table, column scope
    ) -> SemanticModel:
        connector = await self.__get_connector(connector_id)
        sql_connector: SqlConnector = await self._get_sql_connector(connector)

        scope_metadata: List[ScopedTableMetadata] = []

        if not scope_schemas:
            schemas = await sql_connector.fetch_schemas()
        for schema in schemas:
            if not scope_tables:
                scope_tables = [
                    (schema, table)
                    for table in await sql_connector.fetch_tables(schema)
                ]
            for table in scope_tables:
                columns_metadata: List[ColumnMetadata] = []
                table_metadata = TableMetadata(schema=schema, name=table[1])
                columns_metadata = await sql_connector.fetch_columns(schema, table[1])
                if scope_columns:
                    columns_metadata = [
                        column
                        for column in columns_metadata
                        if (column.name) in [col[2] for col in scope_columns]
                    ]
                    
                foreign_keys_metadata = await sql_connector.fetch_foreign_keys(schema, table[1])
                scope_metadata.append(
                    ScopedTableMetadata(
                        schema=schema,
                        table_metadata=table_metadata,
                        columns=columns_metadata,
                        foreign_keys=foreign_keys_metadata,
                    )
                )

        tables: Dict[str, Table] = self._build_semantic_tables(connector, scope_metadata)
        relationships: List[Relationship] = self._infer_relationships(tables, scope_metadata)

        return SemanticModel(
            version="1.0",
            connector=connector.name if isinstance(connector.name, str) else connector.name.value,
            description=f"Semantic Model generated from {connector.name}",
            tables=tables,
            relationships=relationships or None,
        )

    async def build_yaml_for_scope(
        self,
        connector_id: UUID,
    ) -> str:
        semantic_model = await self.build_for_scope(connector_id)
        payload = self.build_sql_analyst_payload(semantic_model)
        return yaml.safe_dump(payload, sort_keys=False)
        
    def parse_yaml_to_model(self, yaml_content: str) -> SemanticModel:
        parsed_dict = yaml.safe_load(yaml_content)
        return SemanticModel.model_validate(parsed_dict)

    def build_sql_analyst_payload(self, semantic_model: SemanticModel) -> Dict[str, Any]:
        """
        Convert a legacy semantic model into the entities-first structure expected by the SQL analyst tool.
        """

        payload: Dict[str, Any] = semantic_model.model_dump(by_alias=True, exclude_none=True)

        entities: Dict[str, Any] = {}
        metrics: Dict[str, Any] = dict(payload.get("metrics") or {})
        dimensions: Dict[str, Any] = dict(payload.get("dimensions") or {})
        joins: List[Dict[str, Any]] = []

        for entity_name, table in semantic_model.tables.items():
            table_columns: Dict[str, Any] = {}
            primary_keys: List[str] = []

            for dimension in table.dimensions or []:
                column_meta: Dict[str, Any] = {
                    "type": dimension.type,
                }
                if dimension.description:
                    column_meta["description"] = dimension.description
                if dimension.synonyms:
                    column_meta["synonyms"] = dimension.synonyms
                if dimension.primary_key:
                    column_meta["role"] = "primary_key"
                    primary_keys.append(dimension.name)
                if dimension.vectorized:
                    column_meta["vectorized"] = True
                table_columns[dimension.name] = column_meta

                dimension_key = f"{entity_name}.{dimension.name}"
                if dimension_key not in dimensions:
                    dimension_entry: Dict[str, Any] = {
                        "entity": entity_name,
                        "column": dimension.name,
                        "type": dimension.type,
                    }
                    if dimension.description:
                        dimension_entry["description"] = dimension.description
                if dimension.synonyms:
                    dimension_entry["synonyms"] = dimension.synonyms
                if dimension.vectorized:
                    dimension_entry["vectorized"] = True
                dimensions[dimension_key] = dimension_entry

            for measure in table.measures or []:
                column_meta = {
                    "type": measure.type,
                    "role": "measure",
                }
                if measure.aggregation:
                    column_meta["aggregation"] = measure.aggregation
                if measure.description:
                    column_meta["description"] = measure.description
                if measure.synonyms:
                    column_meta["synonyms"] = measure.synonyms
                table_columns[measure.name] = column_meta

                metric_key = f"{entity_name}.{measure.name}"
                if metric_key not in metrics:
                    metric_entry: Dict[str, Any] = {
                        "expression": self._build_metric_expression(table, measure),
                    }
                    if measure.aggregation:
                        metric_entry["aggregation"] = measure.aggregation
                    if measure.description:
                        metric_entry["description"] = measure.description
                    if measure.synonyms:
                        metric_entry["synonyms"] = measure.synonyms
                    metrics[metric_key] = metric_entry

            table_payload: Dict[str, Any] = {
                "schema": table.schema,
                "name": table.name,
                "table": f"{table.schema}.{table.name}" if table.schema else table.name,
            }
            if table.description:
                table_payload["description"] = table.description
            if table.synonyms:
                table_payload["synonyms"] = table.synonyms
            if table_columns:
                table_payload["columns"] = table_columns
            if primary_keys:
                table_payload["primary_key"] = primary_keys
            if table.filters:
                table_payload["filters"] = {
                    filter_key: filter_value.model_dump(exclude_none=True)
                    for filter_key, filter_value in table.filters.items()
                }

            entities[entity_name] = table_payload

        for relationship in semantic_model.relationships or []:
            join_entry: Dict[str, Any] = {
                "name": relationship.name,
                "left": relationship.from_,
                "right": relationship.to,
                "on": relationship.join_on,
                "type": "inner",
                "cardinality": relationship.type,
            }
            joins.append(join_entry)

        payload["entities"] = entities
        if joins:
            payload["joins"] = joins
        else:
            payload.pop("joins", None)
        payload["metrics"] = metrics
        payload["dimensions"] = dimensions

        return payload
    
    def _build_semantic_tables(
        self,
        connector: ConnectorResponse,
        scope_metadata: List[ScopedTableMetadata],
    ) -> Dict[str, Table]:
        tables: Dict[str, Table] = {}
        connector_name: str = connector.name if isinstance(connector.name, str) else connector.name.value

        for scope in scope_metadata:
            table_key = self._make_table_key(connector_name, scope.schema, scope.table_metadata.name)
            dimensions: List[Dimension] = []
            dimensions_column_names = set()
            measures: List[Measure] = []

            for column in scope.columns:
                normalized_type = self._map_column_type(column.data_type)

                if normalized_type in {"integer", "decimal", "float"} and "_id" not in column.name.lower():
                    measures.append(
                        Measure(
                            name=column.name,
                            type=normalized_type,
                            aggregation=MeasureAggregation.sum.value,
                            description=f"Aggregate {column.name} from {scope.table_metadata.name}",
                            synonyms=[column.name],
                        )
                    )
                else:
                    is_pk = self._is_probable_primary_key(column.name, scope.table_metadata.name)
                    dimension = Dimension(
                        name=column.name,
                        type=normalized_type,
                        primary_key=is_pk,
                        description=f"Column {column.name} from {scope.table_metadata.name}",
                        synonyms=[column.name],
                    )
                    dimensions.append(dimension)
                    dimensions_column_names.add(column.name.lower())

            tables[table_key] = Table(
                name=scope.table_metadata.name,
                schema=scope.schema,
                description=f"Table {scope.table_metadata.name} from connector {connector_name}",
                synonyms=[
                    scope.table_metadata.name,
                    f"{scope.schema}.{scope.table_metadata.name}"
                ],
                dimensions=dimensions or None,
                measures=measures or None,
            )

        return tables

    def _infer_relationships(self, tables: Dict[str, Table], scope_metadata: List[ScopedTableMetadata]) -> List[Relationship]:
        relationships: List[Relationship] = []
        pk_index: Dict[str, List[Tuple[str, Dimension]]] = defaultdict(list)

        for table_name, table in tables.items():
            for dimension in table.dimensions or []:
                if dimension.primary_key:
                    pk_index[dimension.name.lower()].append((table_name, dimension))
        
        for scoped in scope_metadata:
            for foreign_key in scoped.foreign_keys:
                source_table_key = self._make_table_key(
                    connector_name="",
                    schema=foreign_key.schema,
                    table_name=scoped.table_metadata.name,
                )
                target_table_key = self._make_table_key(
                    connector_name="",
                    schema=foreign_key.schema,
                    table_name=foreign_key.table,
                )
                relationship_name = f"{source_table_key}_to_{target_table_key}"
                join_expression = f"{source_table_key}.{foreign_key.column} = {target_table_key}.{foreign_key.foreign_key}"
                relationships.append(
                    Relationship(
                        name=relationship_name,
                        from_=source_table_key,
                        to=target_table_key,
                        type="many_to_one",
                        join_on=join_expression,
                    )
                )
        
        return relationships
    
    async def __get_column_values_vector(
        self,
        sql_connector: SqlConnector,
        schema: str,
        table_name: str,
        column_name: str,
    ) -> List[Any]:
        query = f"SELECT DISTINCT {column_name} FROM {schema}.{table_name} WHERE {column_name} IS NOT NULL"
        result: QueryResult = await sql_connector.execute(query)
        return [row[0] for row in result.rows]
    
    async def __get_connector(self, connector_id: UUID) -> ConnectorResponse:
        return await self._connector_service.get_connector(connector_id)

    async def _get_sql_connector(self, connector: ConnectorResponse) -> SqlConnector:
        runtime_type = ConnectorRuntimeType(connector.connector_type.upper())
        connector_config = connector.config or {}
        return await self._connector_service.async_create_sql_connector(
            runtime_type,
            connector_config,
        )

    @staticmethod
    def _make_table_key(connector_name: str, schema: str, table_name: str) -> str:
        sanitized = f"{connector_name}_{schema}_{table_name}"
        sanitized = re.sub(r"[^a-zA-Z0-9_]+", "_", sanitized)
        return sanitized.lower()
    

    @staticmethod
    def _map_column_type(data_type: str) -> str:
        normalized = data_type.lower()
        if any(token in normalized for token in TYPE_NUMERIC):
            if "int" in normalized and "point" not in normalized:
                return "integer"
            if any(token in normalized for token in ("double", "float")):
                return "float"
            return "decimal"
        if any(token == normalized or token in normalized for token in TYPE_BOOLEAN):
            return "boolean"
        if any(token == normalized or token in normalized for token in TYPE_DATE) or any(
            token in normalized for token in ("date", "time")
        ):
            return "date"
        return "string"

    @staticmethod
    def _is_probable_primary_key(column_name: str, table_name: str) -> bool:
        normalized_column = column_name.lower()
        normalized_table = re.sub(r"[^a-z0-9]", "", table_name.lower())
        if normalized_column == "id":
            return True
        if normalized_column == f"{normalized_table}id":
            return True
        if normalized_column.endswith("_id") and len(normalized_column) > 3:
            return True
        return False

    @staticmethod
    def _infer_foreign_key_target(
        column_name: str,
        pk_index: Dict[str, List[Tuple[str, Dimension]]],
        current_table: str,
    ) -> Optional[Tuple[str, Dimension]]:
        key = column_name.lower()
        if key not in pk_index:
          return None

    @staticmethod
    def _build_metric_expression(table: Table, measure: Measure) -> str:
        table_ref = f"{table.schema}.{table.name}" if table.schema else table.name
        column_ref = f"{table_ref}.{measure.name}"
        aggregation = (measure.aggregation or "").strip().lower()
        if not aggregation:
            return column_ref
        if aggregation == "count":
            return f"COUNT({column_ref})"
        return f"{aggregation.upper()}({column_ref})"

        for table_name, dimension in pk_index[key]:
            if table_name == current_table:
                continue
            return table_name, dimension
        return None
