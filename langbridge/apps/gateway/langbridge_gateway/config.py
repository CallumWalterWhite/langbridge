"""
Runtime configuration for the database proxy.

Defaults are environment-driven so the proxy can be run in Docker or on the host
without code changes. Adjust the upstream mappings to point at your tenant
databases; the key is matched against the requested database name prefix.
"""


import json
import os
from typing import Dict, NamedTuple


class UpstreamTarget(NamedTuple):
    host: str
    port: int
    database: str | None = None

def _load_upstreams(
    env_name: str,
    default: Dict[str, UpstreamTarget],
) -> Dict[str, UpstreamTarget]:
    """
    Load per-protocol upstream maps from JSON env.

    Expected JSON format:
    {
      "<tenant or tenant__source or *>": {
        "host": "<hostname>",
        "port": 5432,
        "database": "<optional-db-name>"
      }
    }
    """
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return default

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"{env_name} must be a JSON object")

    result: Dict[str, UpstreamTarget] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise ValueError(f"{env_name} key must be a string")
        if not isinstance(value, dict):
            raise ValueError(f"{env_name}.{key} must be an object")
        host = str(value.get("host", "")).strip()
        if not host:
            raise ValueError(f"{env_name}.{key}.host is required")
        port = int(value.get("port", 0))
        if port <= 0:
            raise ValueError(f"{env_name}.{key}.port must be > 0")
        database = value.get("database")
        if database is not None:
            database = str(database).strip() or None
        result[key.strip().lower()] = UpstreamTarget(host=host, port=port, database=database)
    return result


POSTGRES_UPSTREAMS: Dict[str, UpstreamTarget] = _load_upstreams(
    "PROXY_POSTGRES_UPSTREAMS",
    {
        # key -> target. key supports:
        # - tenant (for example "cw_tenant_123")
        # - tenant__source (for example "cw_tenant_123__warehouse")
        # - * (wildcard fallback)
        "cw_tenant_123": UpstreamTarget(host="localhost", port=5432, database="customersdb"),
    },
)

MYSQL_UPSTREAMS: Dict[str, UpstreamTarget] = _load_upstreams(
    "PROXY_MYSQL_UPSTREAMS",
    {
        # key -> target. Supports tenant, tenant__source, and * wildcard.
        "cw_tenant_123": UpstreamTarget(host="localhost", port=3306, database="ordersdb"),
    },
)

# SQL Server upstreams (TDS protocol). key supports tenant, tenant__source, and *.
SQLSERVER_UPSTREAMS: Dict[str, UpstreamTarget] = _load_upstreams(
    "PROXY_SQLSERVER_UPSTREAMS",
    {
        "cw_tenant_123": UpstreamTarget(host="localhost", port=1433, database=None),
    },
)

# Listen settings so containers on the host network can reach us.
LISTEN_HOST = os.environ.get("PROXY_LISTEN_HOST", "0.0.0.0")
PG_LISTEN_PORT = int(os.environ.get("PROXY_PG_PORT", "55432"))
MYSQL_LISTEN_PORT = int(os.environ.get("PROXY_MYSQL_PORT", "53306"))
