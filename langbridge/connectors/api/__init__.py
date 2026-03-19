"""Compatibility namespace for legacy connector imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "langbridge.connectors.base.config": (
        "BaseConnectorConfig",
        "BaseConnectorConfigFactory",
        "BaseConnectorConfigSchemaFactory",
        "ConnectorAuthFieldSchema",
        "ConnectorConfigEntrySchema",
        "ConnectorConfigSchema",
        "ConnectorFamily",
        "ConnectorPluginMetadata",
        "get_connector_config_factory",
        "get_connector_config_schema_factory",
        "ConnectorRuntimeType",
        "ConnectorSyncStrategy",
    ),
    "langbridge.connectors.base.metadata": (
        "BaseMetadataExtractor",
        "ColumnMetadata",
        "TableMetadata",
        "ForeignKeyMetadata",
        "get_metadata_extractor",
        "build_connector_config",
    ),
    "langbridge.connectors.base.connector": (
        "ConnectorError",
        "AuthError",
        "ApiConnector",
        "ApiExtractResult",
        "ApiResource",
        "ApiSyncResult",
        "SqlDialetcs",
        "VectorDBType",
        "Connector",
        "ConnectorType",
        "SqlConnector",
        "VecotorDBConnector",
        "ManagedVectorDB",
        "NoSqlConnector",
        "NoSqlQueryResult",
        "QueryResult",
        "ConnectorRuntimeTypeSqlDialectMap",
        "ConnectorRuntimeTypeVectorDBMap",
        "run_sync",
    ),
    "langbridge.connectors.base.registry": (
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
    ),
}

_MODULE_EXPORTS = {
    "_http_api_connector": "langbridge.connectors.base.http",
}

__all__ = [name for names in _EXPORTS.values() for name in names] + list(
    _MODULE_EXPORTS
)


def __getattr__(name: str) -> Any:
    module_name = _MODULE_EXPORTS.get(name)
    if module_name is not None:
        module = import_module(module_name)
        globals()[name] = module
        return module

    for module_name, exports in _EXPORTS.items():
        if name not in exports:
            continue
        module = import_module(module_name)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
