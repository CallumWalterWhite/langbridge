"""
Connector registry responsible for managing available connectors.
"""

from logging import Logger
from typing import Type

from .config import BaseConnectorConfig
from .connector import SqlDialetcs, SqlConnector, VecotorDBConnector, VectorDBType

class SqlConnectorFactory:
    """Factory for creating connectors."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def get_sql_connector_class_reference(sql_dialetc: SqlDialetcs) -> Type[SqlConnector]:
        subclasses = SqlConnector.__subclasses__()
        for subclass in subclasses:
            if subclass.DIALECT == sql_dialetc:
                return subclass
        raise ValueError(f"No connector found for dialect: {sql_dialetc}")
    
    @staticmethod
    def create_sql_connector(
        sql_dialetc: SqlDialetcs, 
        config: BaseConnectorConfig,
        logger: Logger) -> SqlConnector:
        connector_class = SqlConnectorFactory.get_sql_connector_class_reference(sql_dialetc)
        return connector_class(config=config, logger=logger)


class VectorDBConnectorFactory:
    """Factory for creating vector database connectors."""

    @staticmethod
    def get_vector_connector_class_reference(vector_db: VectorDBType) -> Type[VecotorDBConnector]:
        subclasses = VecotorDBConnector.__subclasses__()
        for subclass in subclasses:
            if subclass.VECTOR_DB_TYPE == vector_db:
                return subclass
        raise ValueError(f"No vector connector found for type: {vector_db}")

    @staticmethod
    def create_vector_connector(
        vector_db: VectorDBType,
        config: BaseConnectorConfig,
        logger: Logger,
    ) -> VecotorDBConnector:
        connector_class = VectorDBConnectorFactory.get_vector_connector_class_reference(vector_db)
        return connector_class(config=config, logger=logger)
    
class ConnectorInstanceRegistry:
    """Registry for managing connector instances."""

    def __init__(self) -> None:
        self._connectors: dict[str, SqlConnector] = {}

    def add(self, connector: SqlConnector, name: str) -> None:
        self._connectors[name] = connector
        
    def get(self, name: str) -> SqlConnector:
        return self._connectors[name]

    def delete(self, name: str) -> None:
        del self._connectors[name]

__all__ = ["SqlConnectorFactory", "VectorDBConnectorFactory", "ConnectorInstanceRegistry"]
