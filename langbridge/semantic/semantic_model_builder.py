

from dataclasses import dataclass
import json
import logging
import re
import yaml
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from connectors import (
    BaseConnectorConfig,
    ConnectorRuntimeType,
    TableMetadata,
    ColumnMetadata,
    ForeignKeyMetadata,
    build_connector_config,
    SqlConnector,
    SqlConnectorFactory,
    ConnectorRuntimeTypeSqlDialectMap
)
from db.connector import Connector
from errors.application_errors import BusinessValidationError
from semantic.model import MeasureAggregation
from repositories.connector_repository import ConnectorRepository
from repositories.organization_repository import OrganizationRepository, ProjectRepository

from semantic import Dimension, Measure, Relationship, SemanticModel, Table

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
        connector_repository: ConnectorRepository,
        organization_repository: OrganizationRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._connector_repository = connector_repository
        self._organization_repository = organization_repository
        self._project_repository = project_repository
        self._sql_connector_factory = SqlConnectorFactory()
        self._logger = logging.getLogger(__name__)

    def build_for_scope(
        self,
        connector_id: UUID,
        scope_schemas: Optional[List[str]] = None, # schema scope
        scope_tables: Optional[List[Tuple[str, str]]] = None, # schema, table scope
        scope_columns: Optional[List[Tuple[str, str, str]]] = None, # schema, table, column scope
    ) -> SemanticModel:
        connector: Optional[Connector] = self.__get_connector(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found")
        sql_connector = self._get_sql_connector(connector)

        scope_metadata: List[ScopedTableMetadata] = []

        if not scope_schemas:
            schemas = sql_connector.fetch_schemas_sync()
        for schema in schemas:
            if not scope_tables:
                scope_tables = [
                    (schema, table)
                    for table in sql_connector.fetch_tables_sync(schema)
                ]
            for table in scope_tables:
                columns_metadata: List[ColumnMetadata] = []
                table_metadata = TableMetadata(schema=schema, name=table[1])
                columns_metadata = sql_connector.fetch_columns_sync(schema, table[1])
                if scope_columns:
                    columns_metadata = [
                        column
                        for column in columns_metadata
                        if (column.name) in [col[2] for col in scope_columns]
                    ]
                foreign_keys_metadata = sql_connector.fetch_foreign_keys_sync(schema, table[1])
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

    def build_yaml_for_scope(
        self,
        connector_id: UUID,
    ) -> str:
        semantic_model = self.build_for_scope(connector_id)
        return yaml.safe_dump(
            semantic_model.model_dump(by_alias=True, exclude_none=True),
            sort_keys=False,
        )
        
    def parse_yaml_to_model(self, yaml_content: str) -> SemanticModel:
        parsed_dict = yaml.safe_load(yaml_content)
        return SemanticModel.model_validate(parsed_dict)
    
    def _build_semantic_tables(
        self,
        connector: Connector,
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

        for table_name, table in tables.items():
            for dimension in table.dimensions or []:
                if dimension.primary_key:
                    continue
                
                # Use foregin metadata to infer relationships

                scoped_metadata: ScopedTableMetadata | None = next(
                    (sm for sm in scope_metadata if table.name == sm.table_metadata.name and sm.schema == table.schema),
                    None
                )

                if scoped_metadata:
                    foreign_keys_metadata = scoped_metadata.foreign_keys
                    if foreign_keys_metadata:
                        for foreign_key in foreign_keys_metadata:
                            if foreign_key.column == dimension.name:
                                target_table = foreign_key.foreign_key
                                target_dimension = foreign_key.primary_key
                                relationship_name = f"{table_name}_to_{target_table}"
                                join_expression = f"{table_name}.{dimension.name} = {target_table}.{target_dimension}"
                                relationships.append(
                                    Relationship(
                                        name=relationship_name,
                                        from_=table_name,
                                        to=target_table,
                                        type="many_to_one",
                                        join_on=join_expression,
                                    )
                                )
                else:
                    fk_target = self._infer_foreign_key_target(dimension.name, pk_index, table_name)
                    if not fk_target:
                        continue

                    target_table, target_dimension = fk_target
                    relationship_name = f"{table_name}_to_{target_table}"
                    join_expression = f"{table_name}.{dimension.name} = {target_table}.{target_dimension.name}"

                    relationships.append(
                        Relationship(
                            name=relationship_name,
                            from_=table_name,
                            to=target_table,
                            type="many_to_one",
                            join_on=join_expression,
                        )
                    )
        return relationships
    
    def __get_connector(self, connector_id: UUID) -> Connector:
        connector: Connector | None = self._connector_repository.get_by_id(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found")
        return connector
    
    def __get_connector_config(self, connector: Connector) -> BaseConnectorConfig:
        config_payload = json.loads(connector.config_json if isinstance(connector.config_json, str) else connector.config_json.value)
        if hasattr(config_payload, "to_dict"):
            config_payload = config_payload.to_dict()
        connector_runtime = ConnectorRuntimeType(connector.connector_type.upper())
        config: BaseConnectorConfig = build_connector_config(connector_runtime, config_payload['config'])
        return config
    
    def _get_sql_connector(self, connector: Connector) -> SqlConnector:
        connector_config: BaseConnectorConfig = self.__get_connector_config(connector)
        runtime_type = ConnectorRuntimeType(connector.connector_type.upper())
        sql_connector: SqlConnector = self._sql_connector_factory.create_sql_connector(
            ConnectorRuntimeTypeSqlDialectMap[runtime_type],
            connector_config,
            logger=self._logger
        )
        sql_connector.test_connection_sync()
        return sql_connector

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

        for table_name, dimension in pk_index[key]:
            if table_name == current_table:
                continue
            return table_name, dimension
        return None
