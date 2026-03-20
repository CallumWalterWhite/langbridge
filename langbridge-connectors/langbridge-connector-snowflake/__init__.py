from importlib import import_module
from typing import Any

from langbridge.plugins import (
    ConnectorFamily,
    ConnectorPlugin,
    ConnectorRuntimeType,
    register_connector_plugin,
)

from .config import (
    SnowflakeConnectorConfig,
    SnowflakeConnectorConfigFactory,
    SnowflakeConnectorConfigSchemaFactory,
)

register_connector_plugin(
    ConnectorPlugin(
        connector_type=ConnectorRuntimeType.SNOWFLAKE,
        connector_family=ConnectorFamily.DATABASE,
        config_factory=SnowflakeConnectorConfigFactory,
        config_schema_factory=SnowflakeConnectorConfigSchemaFactory,
    )
)

_LAZY_EXPORTS = {
    "SnowflakeConnector": ".connector",
}

__all__ = [
    "SnowflakeConnector",
    "SnowflakeConnectorConfig",
    "SnowflakeConnectorConfigFactory",
    "SnowflakeConnectorConfigSchemaFactory",
]


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
