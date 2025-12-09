"""
Runtime configuration for the database proxy.

Defaults are environment-driven so the proxy can be run in Docker or on the host
without code changes. Adjust the upstream mappings to point at your tenant
databases; the key is matched against the requested database name prefix.
"""


import os
from typing import Dict, NamedTuple


class UpstreamTarget(NamedTuple):
    host: str
    port: int
    database: str | None = None

POSTGRES_UPSTREAMS: Dict[str, UpstreamTarget] = {
    # prefix -> target; database override lets you map any tenant prefix to a shared upstream DB.
    "cw_tenant_123": UpstreamTarget(host="localhost", port=5432, database="customersdb"),
}

MYSQL_UPSTREAMS: Dict[str, UpstreamTarget] = {
    # Map cw_tenant_123 to ordersdb upstream.
    "cw_tenant_123": UpstreamTarget(host="localhost", port=3306, database="ordersdb"),
}

# Listen settings so containers on the host network can reach us.
LISTEN_HOST = os.environ.get("PROXY_LISTEN_HOST", "0.0.0.0")
PG_LISTEN_PORT = int(os.environ.get("PROXY_PG_PORT", "55432"))
MYSQL_LISTEN_PORT = int(os.environ.get("PROXY_MYSQL_PORT", "53306"))
