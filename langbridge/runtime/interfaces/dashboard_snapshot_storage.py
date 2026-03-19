"""Compatibility wrapper for dashboard snapshot storage protocols."""

from langbridge.runtime.ports import (  # noqa: F401
    IDashboardSnapshotDeleter,
    IDashboardSnapshotReader,
    IDashboardSnapshotStorage,
    IDashboardSnapshotWriter,
)

__all__ = [
    "IDashboardSnapshotDeleter",
    "IDashboardSnapshotReader",
    "IDashboardSnapshotStorage",
    "IDashboardSnapshotWriter",
]
