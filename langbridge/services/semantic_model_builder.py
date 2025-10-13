from __future__ import annotations

import json
import logging
import re
import yaml
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from connectors import (
    ConnectorType,
    TableMetadata,
    build_connector_config,
    get_metadata_extractor,
)
from db.auth import Organization
from db.connector import Connector
from errors.application_errors import BusinessValidationError
from repositories.connector_repository import ConnectorRepository
from repositories.organization_repository import OrganizationRepository, ProjectRepository
from semantic import Dimension, Measure, Relationship, SemanticModel, Table

logger = logging.getLogger(__name__)


TYPE_NUMERIC = {"number", "decimal", "numeric", "int", "integer", "float", "double", "real"}
TYPE_BOOLEAN = {"boolean", "bool"}
TYPE_DATE = {"date", "datetime", "timestamp", "time"}


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

    def build_for_scope(
        self,
        organization_id: UUID,
        project_id: Optional[UUID] = None,
    ) -> SemanticModel:
        organization = self._organization_repository.get_by_id(organization_id)
        if not organization:
            raise BusinessValidationError("Organization not found")

        connectors = self._collect_connectors(organization, project_id)
        table_metadata = self._collect_metadata_from_connectors(connectors)

        tables = self._build_tables(table_metadata)
        relationships = self._infer_relationships(tables)

        return SemanticModel(
            version="1.0",
            database="langbridge",
            description="Semantic model generated from LangBridge connectors.",
            tables=tables,
            relationships=relationships or None,
        )

    def build_yaml_for_scope(
        self,
        organization_id: UUID,
        project_id: Optional[UUID] = None,
    ) -> str:
        semantic_model = self.build_for_scope(organization_id=organization_id, project_id=project_id)
        return yaml.safe_dump(
            semantic_model.model_dump(by_alias=True, exclude_none=True),
            sort_keys=False,
        )

    def _collect_connectors(
        self,
        organization: Organization,
        project_id: Optional[UUID],
    ) -> Sequence[Connector]:
        if project_id:
            project = self._project_repository.get_by_id(project_id)
            if not project:
                raise BusinessValidationError("Project not found")
            if project.organization_id != organization.id:
                raise BusinessValidationError("Project does not belong to the specified organization")
            return project.connectors

        return organization.connectors

    def _collect_metadata_from_connectors(
        self,
        connectors: Sequence[Connector],
    ) -> Dict[str, Tuple[Connector, List[TableMetadata]]]:
        metadata_map: Dict[str, Tuple[Connector, List[TableMetadata]]] = {}

        for connector in connectors:
            try:
                connector_type = ConnectorType(connector.connector_type.upper())
            except ValueError:
                logger.warning("Skipping connector '%s': unsupported type '%s'", connector.name, connector.connector_type)
                continue

            try:
                config_payload = json.loads(connector.config_json or "{}").get("config", {})
                config = build_connector_config(connector_type, config_payload)
                extractor = get_metadata_extractor(connector_type)
                tables_metadata = extractor.fetch_metadata(config)
                metadata_map[connector.id.hex] = (connector, tables_metadata)
            except BusinessValidationError as exc:
                logger.warning("Skipping connector '%s' due to metadata extraction error: %s", connector.name, exc)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping connector '%s': invalid configuration JSON (%s)", connector.name, exc)

        return metadata_map

    def _build_tables(
        self,
        metadata_map: Dict[str, Tuple[Connector, List[TableMetadata]]],
    ) -> Dict[str, Table]:
        tables: Dict[str, Table] = {}

        for _, (connector, table_list) in metadata_map.items():
            for table_meta in table_list:
                table_key = self._make_table_key(connector.name, table_meta.schema, table_meta.name)
                dimensions: List[Dimension] = []
                measures: List[Measure] = []

                for column in table_meta.columns:
                    normalized_type = self._map_column_type(column.data_type)
                    is_pk = self._is_probable_primary_key(column.name, table_meta.name)
                    dimension = Dimension(
                        name=column.name,
                        type=normalized_type,
                        primary_key=is_pk,
                    )
                    dimensions.append(dimension)

                    if normalized_type in {"integer", "decimal", "float"}:
                        measures.append(
                            Measure(
                                name=column.name,
                                type=normalized_type,
                                aggregation="sum",
                                description=f"Aggregate {column.name} from {table_meta.name}",
                            )
                        )

                tables[table_key] = Table(
                    description=f"Table {table_meta.name} from connector {connector.name}",
                    synonyms=[
                        table_meta.name,
                        f"{table_meta.schema}.{table_meta.name}",
                        connector.name,
                    ],
                    dimensions=dimensions or None,
                    measures=measures or None,
                )

        return tables

    def _infer_relationships(self, tables: Dict[str, Table]) -> List[Relationship]:
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
