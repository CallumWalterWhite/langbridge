"""Routing helpers shared across protocol implementations."""

from __future__ import annotations

from config import MYSQL_UPSTREAMS, POSTGRES_UPSTREAMS, UpstreamTarget


def route_database(db_name: str, db_type: str) -> UpstreamTarget:
    """
    Select an upstream based on the requested database prefix.

    Raises ValueError if the database does not match a known tenant.
    """
    lowered = (db_name or "").lower()
    if db_type == "postgres":
        for prefix, upstream in POSTGRES_UPSTREAMS.items():
            if lowered.startswith(prefix):
                return upstream
    elif db_type == "mysql":
        for prefix, upstream in MYSQL_UPSTREAMS.items():
            if lowered.startswith(prefix):
                return upstream

    raise ValueError(f"Unknown tenant for {db_type}: {db_name}")
