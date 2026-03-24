from .config import (
    GITHUB_AUTH_SCHEMA,
    GITHUB_MANIFEST,
    GITHUB_SUPPORTED_RESOURCES,
    GITHUB_SYNC_STRATEGY,
    GitHubDeclarativeConnectorConfig,
    GitHubDeclarativeConnectorConfigFactory,
    GitHubDeclarativeConnectorConfigSchemaFactory,
)
from .connector import GitHubDeclarativeApiConnector
from .examples import DeclarativeDatasetExampleSet, load_dataset_examples
from .plugin import PLUGIN, get_connector_plugin, register_plugin

__all__ = [
    "DeclarativeDatasetExampleSet",
    "GITHUB_AUTH_SCHEMA",
    "GITHUB_MANIFEST",
    "GITHUB_SUPPORTED_RESOURCES",
    "GITHUB_SYNC_STRATEGY",
    "GitHubDeclarativeApiConnector",
    "GitHubDeclarativeConnectorConfig",
    "GitHubDeclarativeConnectorConfigFactory",
    "GitHubDeclarativeConnectorConfigSchemaFactory",
    "PLUGIN",
    "get_connector_plugin",
    "load_dataset_examples",
    "register_plugin",
]
