"""Compatibility wrappers for the pre-convergence runtime interface namespace."""

from langbridge.runtime.events import AgentEventEmitter as IAgentEventEmitter
from langbridge.runtime.events import AgentEventVisibility
from langbridge.runtime.ports import (
    IConnectorStore,
    IDashboardSnapshotDeleter,
    IDashboardSnapshotReader,
    IDashboardSnapshotStorage,
    IDashboardSnapshotWriter,
    ISemanticModelStore,
)

__all__ = [
    "AgentEventVisibility",
    "IAgentEventEmitter",
    "IConnectorStore",
    "IDashboardSnapshotReader",
    "IDashboardSnapshotWriter",
    "IDashboardSnapshotDeleter",
    "IDashboardSnapshotStorage",
    "ISemanticModelStore",
]
