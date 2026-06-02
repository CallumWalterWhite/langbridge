from __future__ import annotations

from enum import Enum

from pydantic import Field

from .base import _BaseModel


class ConnectorConfig(_BaseModel):
    """Base class for a connector's typed, validated runtime configuration.

    Each connector defines its own subclass declaring the fields it needs
    (host, credentials, paths, ...). Instances are what a connector is
    constructed with. This is distinct from `ConnectorConfigSchema`, which
    *describes* those fields for discovery before instantiation.
    """


class ConnectorConfigEntrySchema(_BaseModel):
    field: str = Field(..., description="The name of the configuration field")
    label: str | None = Field(None, description="A human-readable label for the configuration field")
    required: bool = Field(..., description="Whether the configuration field is required")
    default: str | None = Field(None, description="The default value for the configuration field, if any")
    description: str = Field(..., description="A brief description of the configuration field")
    type: str = Field(..., description="The data type of the configuration field")
    secret: bool = Field(False, description="Whether this field holds a secret value (e.g. API key, password)")
    value_list: list[str] | None = Field(None, description="Valid values for enum-style fields")


class ConnectorCapabilities(_BaseModel):
    supports_live_datasets: bool = Field(False, description="Whether the connector supports live datasets")
    supports_synced_datasets: bool = Field(False, description="Whether the connector supports synced datasets")
    supports_incremental_sync: bool = Field(False, description="Whether the connector supports incremental synchronization")
    supports_query_pushdown: bool = Field(False, description="Whether the connector supports query pushdown")
    supports_preview: bool = Field(False, description="Whether the connector supports previewing data")
    supports_federated_execution: bool = Field(False, description="Whether the connector supports federated execution")


class ConnectorSyncStrategy(str, Enum):
    FULL_REFRESH = "FULL_REFRESH"
    INCREMENTAL = "INCREMENTAL"
    WINDOWED_INCREMENTAL = "WINDOWED_INCREMENTAL"
    MANUAL = "MANUAL"


class ConnectorPluginMetadata(_BaseModel):
    default_sync_strategy: ConnectorSyncStrategy | None = Field(None, description="The default synchronization strategy for the connector")
    capabilities: ConnectorCapabilities = Field(default_factory=ConnectorCapabilities, description="The capabilities of the connector plugin")  # type: ignore[arg-type]


class ConnectorConfigSchema(_BaseModel):
    name: str = Field(..., description="The name of the connector")
    description: str = Field(..., description="A brief description of the connector")
    version: str = Field(..., description="The version of the configuration schema")
    config: list[ConnectorConfigEntrySchema] = Field(..., description="Configuration fields required to instantiate this connector")
    plugin_metadata: ConnectorPluginMetadata | None = Field(None, description="Capability and sync metadata for this connector")
