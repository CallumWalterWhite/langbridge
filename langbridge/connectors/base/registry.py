"""
Connector registry responsible for managing available connectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from logging import Logger
from typing import TYPE_CHECKING, Type

from .config import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorAuthFieldSchema,
    ConnectorFamily,
    ConnectorRuntimeType,
    ConnectorSyncStrategy,
)

if TYPE_CHECKING:
    from .connector import (
        ApiConnector,
        Connector,
        ManagedVectorDB,
        NoSqlConnector,
        SqlDialetcs,
        SqlConnector,
        VecotorDBConnector,
        VectorDBType,
    )

_BUILTIN_PLUGIN_MODULES = (
    "langbridge.connectors.saas.shopify",
    "langbridge.connectors.saas.stripe",
    "langbridge.connectors.saas.hubspot",
    "langbridge.connectors.saas.google_analytics",
    "langbridge.connectors.saas.salesforce",
)
_BUILTIN_CONNECTOR_MODULES = (
    "langbridge.connectors.sql.snowflake",
    "langbridge.connectors.builtin.postgres",
    "langbridge.connectors.builtin.mysql",
    "langbridge.connectors.sql.mariadb",
    "langbridge.connectors.nosql.mongodb",
    "langbridge.connectors.sql.redshift",
    "langbridge.connectors.sql.bigquery",
    "langbridge.connectors.sql.sqlserver",
    "langbridge.connectors.sql.oracle",
    "langbridge.connectors.builtin.sqlite",
    "langbridge.connectors.vector.faiss",
    "langbridge.connectors.vector.qdrant",
    *_BUILTIN_PLUGIN_MODULES,
)

_builtin_plugins_loaded = False
_builtin_connectors_loaded = False


def ensure_builtin_plugins_loaded() -> None:
    global _builtin_plugins_loaded

    if _builtin_plugins_loaded:
        return

    for module_path in _BUILTIN_PLUGIN_MODULES:
        import_module(module_path)

    _builtin_plugins_loaded = True


def ensure_builtin_connectors_loaded() -> None:
    global _builtin_connectors_loaded

    if _builtin_connectors_loaded:
        return

    for module_path in _BUILTIN_CONNECTOR_MODULES:
        import_module(module_path)

    _builtin_connectors_loaded = True


@dataclass(frozen=True, slots=True)
class ConnectorPlugin:
    connector_type: ConnectorRuntimeType
    connector_family: ConnectorFamily
    supported_resources: tuple[str, ...] = ()
    auth_schema: tuple[ConnectorAuthFieldSchema, ...] = ()
    sync_strategy: ConnectorSyncStrategy | None = None
    config_factory: Type[BaseConnectorConfigFactory] | None = None
    config_schema_factory: Type[BaseConnectorConfigSchemaFactory] | None = None
    api_connector_class: Type[ApiConnector] | None = None


class ConnectorPluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[ConnectorRuntimeType, ConnectorPlugin] = {}

    def register(self, plugin: ConnectorPlugin) -> ConnectorPlugin:
        self._plugins[plugin.connector_type] = plugin
        return plugin

    def get(self, connector_type: ConnectorRuntimeType) -> ConnectorPlugin | None:
        return self._plugins.get(connector_type)

    def list(self) -> list[ConnectorPlugin]:
        return list(self._plugins.values())


_plugin_registry = ConnectorPluginRegistry()


def register_connector_plugin(plugin: ConnectorPlugin) -> ConnectorPlugin:
    return _plugin_registry.register(plugin)


def get_connector_plugin(connector_type: ConnectorRuntimeType) -> ConnectorPlugin | None:
    ensure_builtin_plugins_loaded()
    return _plugin_registry.get(connector_type)


def list_connector_plugins() -> list[ConnectorPlugin]:
    ensure_builtin_plugins_loaded()
    return _plugin_registry.list()


class SqlConnectorFactory:
    """Factory for creating connectors."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def get_sql_connector_class_reference(sql_dialetc: SqlDialetcs) -> Type[SqlConnector]:
        from .connector import SqlConnector

        ensure_builtin_connectors_loaded()
        subclasses = SqlConnector.__subclasses__()
        for subclass in subclasses:
            if subclass.DIALECT == sql_dialetc:
                return subclass
        raise ValueError(f"No connector found for dialect: {sql_dialetc}")

    @staticmethod
    def create_sql_connector(
        sql_dialetc: SqlDialetcs,
        config: BaseConnectorConfig,
        logger: Logger,
    ) -> SqlConnector:
        connector_class = SqlConnectorFactory.get_sql_connector_class_reference(sql_dialetc)
        return connector_class(config=config, logger=logger)


class ApiConnectorFactory:
    """Factory for creating API connectors from the plugin registry."""

    @staticmethod
    def get_api_connector_class_reference(
        connector_type: ConnectorRuntimeType,
    ) -> Type[ApiConnector]:
        from .connector import ApiConnector

        plugin = get_connector_plugin(connector_type)
        if plugin is not None and plugin.api_connector_class is not None:
            return plugin.api_connector_class

        for subclass in ApiConnector.__subclasses__():
            if getattr(subclass, "RUNTIME_TYPE", None) == connector_type:
                return subclass

        raise ValueError(f"No API connector found for runtime type: {connector_type}")

    @staticmethod
    def create_api_connector(
        connector_type: ConnectorRuntimeType,
        config: BaseConnectorConfig,
        logger: Logger,
    ) -> ApiConnector:
        connector_class = ApiConnectorFactory.get_api_connector_class_reference(
            connector_type
        )
        return connector_class(config=config, logger=logger)


class NoSqlConnectorFactory:
    """Factory for creating document database connectors."""

    @staticmethod
    def get_no_sql_connector_class_reference(
        connector_type: ConnectorRuntimeType,
    ) -> Type[NoSqlConnector]:
        from .connector import NoSqlConnector

        ensure_builtin_connectors_loaded()
        subclasses = NoSqlConnector.__subclasses__()
        for subclass in subclasses:
            if getattr(subclass, "RUNTIME_TYPE", None) == connector_type:
                return subclass
        raise ValueError(f"No no-sql connector found for runtime type: {connector_type}")

    @staticmethod
    def create_no_sql_connector(
        connector_type: ConnectorRuntimeType,
        config: BaseConnectorConfig,
        logger: Logger,
    ) -> NoSqlConnector:
        connector_class = NoSqlConnectorFactory.get_no_sql_connector_class_reference(
            connector_type
        )
        return connector_class(config=config, logger=logger)


class VectorDBConnectorFactory:
    """Factory for creating vector database connectors."""

    @staticmethod
    def get_vector_connector_class_reference(
        vector_db: VectorDBType,
    ) -> Type[VecotorDBConnector]:
        from .connector import VecotorDBConnector

        ensure_builtin_connectors_loaded()
        subclasses = VecotorDBConnector.__subclasses__()
        for subclass in subclasses:
            if subclass.VECTOR_DB_TYPE == vector_db:
                return subclass
        raise ValueError(f"No vector connector found for type: {vector_db}")

    @staticmethod
    def get_managed_vector_db_class_reference(
        vector_db: VectorDBType,
    ) -> Type[ManagedVectorDB]:
        from .connector import ManagedVectorDB

        ensure_builtin_connectors_loaded()
        subclasses = ManagedVectorDB.__subclasses__()
        for subclass in subclasses:
            if subclass.VECTOR_DB_TYPE == vector_db:
                return subclass
        raise ValueError(f"No managed vector DB found for type: {vector_db}")

    @staticmethod
    def get_all_managed_vector_dbs() -> list[VectorDBType]:
        from .connector import ManagedVectorDB

        ensure_builtin_connectors_loaded()
        managed_vector_dbs = []
        subclasses = ManagedVectorDB.__subclasses__()
        for subclass in subclasses:
            managed_vector_dbs.append(subclass.VECTOR_DB_TYPE)
        return managed_vector_dbs

    @staticmethod
    def create_vector_connector(
        vector_db: VectorDBType,
        config: BaseConnectorConfig,
        logger: Logger,
    ) -> VecotorDBConnector:
        connector_class = VectorDBConnectorFactory.get_vector_connector_class_reference(
            vector_db
        )
        return connector_class(config=config, logger=logger)


class ConnectorInstanceRegistry:
    """Registry for managing connector instances."""

    def __init__(self) -> None:
        self._connectors: dict[str, Connector] = {}

    def add(self, connector: Connector, name: str) -> None:
        self._connectors[name] = connector

    def get(self, name: str) -> Connector:
        return self._connectors[name]

    def delete(self, name: str) -> None:
        del self._connectors[name]


__all__ = [
    "ApiConnectorFactory",
    "ConnectorInstanceRegistry",
    "ConnectorPlugin",
    "ConnectorPluginRegistry",
    "NoSqlConnectorFactory",
    "SqlConnectorFactory",
    "VectorDBConnectorFactory",
    "ensure_builtin_connectors_loaded",
    "ensure_builtin_plugins_loaded",
    "get_connector_plugin",
    "list_connector_plugins",
    "register_connector_plugin",
]
