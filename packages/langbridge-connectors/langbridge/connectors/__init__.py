"""langbridge-connectors — the connector framework and builtin connectors.

The framework defines the connector base types, the typed catalog/protocol
models, and a registry. Builtin connectors (postgres, mysql, sqlite, files)
are registered into the default :data:`registry` at import time.
"""

from .base import BaseConnector, TConfig
from .declarative import DeclarativeConnector
from .errors import (
    ConnectorAuthError,
    ConnectorConfigError,
    ConnectorConnectionError,
    ConnectorError,
    ConnectorNotRegisteredError,
    MissingDependencyError,
    QueryExecutionError,
    QueryValidationError,
    ResourceNotFoundError,
)
from .models import (
    ConnectorCapabilities,
    ConnectorConfig,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorPluginMetadata,
    ConnectorSyncStrategy,
    FieldType,
    LangbridgeCatalog,
    LangbridgeField,
    LangbridgeQueryRequest,
    LangbridgeResource,
    LangbridgeSyncRequest,
)
from .registry import ConnectorRegistry, registry
from .source import SourceConnector
from .sql import SqlConnector
from ._builtin import BUILTIN_CONNECTORS, register_builtins

register_builtins(registry)

__all__ = [
    # Base types
    "BaseConnector",
    "TConfig",
    "SourceConnector",
    "SqlConnector",
    "DeclarativeConnector",
    # Registry
    "ConnectorRegistry",
    "registry",
    "BUILTIN_CONNECTORS",
    "register_builtins",
    # Errors
    "ConnectorError",
    "ConnectorConfigError",
    "ConnectorConnectionError",
    "ConnectorAuthError",
    "ConnectorNotRegisteredError",
    "MissingDependencyError",
    "QueryExecutionError",
    "QueryValidationError",
    "ResourceNotFoundError",
    # Models
    "ConnectorCapabilities",
    "ConnectorConfig",
    "ConnectorConfigEntrySchema",
    "ConnectorConfigSchema",
    "ConnectorPluginMetadata",
    "ConnectorSyncStrategy",
    "FieldType",
    "LangbridgeCatalog",
    "LangbridgeField",
    "LangbridgeQueryRequest",
    "LangbridgeResource",
    "LangbridgeSyncRequest",
]
