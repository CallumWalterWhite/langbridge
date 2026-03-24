"""Shared declarative SaaS connector contracts and helpers."""

from .config import (
    build_declarative_auth_schema,
    build_declarative_config_entries,
    build_declarative_connector_config_schema,
    build_declarative_plugin_metadata,
)
from .examples import (
    DeclarativeDatasetConnectorReference,
    DeclarativeDatasetExample,
    DeclarativeDatasetExampleSet,
    DatasetSyncSelection,
    CustomDatasetResource,
    load_declarative_dataset_examples,
)
from .manifest import (
    DeclarativeAuthConfig,
    DeclarativeAuthHeader,
    DeclarativeConnectorManifest,
    DeclarativeConnectorResource,
    DeclarativeIncrementalConfig,
    DeclarativePaginationConfig,
    load_declarative_connector_manifest,
)
from .runtime import DeclarativeHttpApiConnector

__all__ = [
    "DeclarativeAuthConfig",
    "DeclarativeAuthHeader",
    "DeclarativeConnectorManifest",
    "DeclarativeConnectorResource",
    "DeclarativeDatasetConnectorReference",
    "DeclarativeDatasetExample",
    "DeclarativeDatasetExampleSet",
    "DeclarativeIncrementalConfig",
    "DeclarativePaginationConfig",
    "CustomDatasetResource",
    "DatasetSyncSelection",
    "build_declarative_auth_schema",
    "build_declarative_config_entries",
    "build_declarative_connector_config_schema",
    "build_declarative_plugin_metadata",
    "DeclarativeHttpApiConnector",
    "load_declarative_dataset_examples",
    "load_declarative_connector_manifest",
]
