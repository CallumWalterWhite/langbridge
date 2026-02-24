"""Routing helpers shared across protocol implementations."""

from __future__ import annotations

from typing import Iterable

from .config import MYSQL_UPSTREAMS, POSTGRES_UPSTREAMS, SQLSERVER_UPSTREAMS, UpstreamTarget


IDENTITY_SEPARATOR = "__"


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _parse_routing_identity(db_name: str | None, user_name: str | None) -> tuple[str, str | None]:
    """
    Resolve tenant/source routing identity from database and user values.

    Priority:
    1. Database token from JDBC URL, supporting `tenant` and `tenant__source`.
    2. Username token with segments like `tenant:<id>;source:<id>`.
    """
    db_token = _normalize(db_name)
    if db_token:
        if IDENTITY_SEPARATOR in db_token:
            tenant, source = db_token.split(IDENTITY_SEPARATOR, 1)
            return tenant, source or None
        return db_token, None

    user_token = _normalize(user_name)
    if user_token:
        tenant: str | None = None
        source: str | None = None
        for segment in user_token.replace("|", ";").replace(",", ";").split(";"):
            if ":" not in segment:
                continue
            key, value = segment.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not value:
                continue
            if key == "tenant":
                tenant = value
            elif key == "source":
                source = value
        if tenant:
            return tenant, source

    return "", None


def _iter_candidates(db_name: str, tenant: str, source: str | None) -> Iterable[str]:
    seen: set[str] = set()

    for value in [
        _normalize(db_name),
        f"{tenant}{IDENTITY_SEPARATOR}{source}" if tenant and source else "",
        tenant,
    ]:
        if value and value not in seen:
            seen.add(value)
            yield value


def route_database(db_name: str, db_type: str, user_name: str | None = None) -> UpstreamTarget:
    """
    Select an upstream based on the requested database prefix.

    Raises ValueError if the database does not match a known tenant.
    """
    tenant, source = _parse_routing_identity(db_name, user_name)
    lowered = _normalize(db_name)

    if db_type == "postgres":
        upstreams = POSTGRES_UPSTREAMS
    elif db_type == "mysql":
        upstreams = MYSQL_UPSTREAMS
    elif db_type == "sqlserver":
        upstreams = SQLSERVER_UPSTREAMS
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    # First pass: exact key matches.
    for candidate in _iter_candidates(lowered, tenant, source):
        exact = upstreams.get(candidate)
        if exact:
            return exact

    # Second pass: prefix fallback for backwards compatibility.
    sorted_prefixes = sorted(upstreams.items(), key=lambda item: len(item[0]), reverse=True)
    for candidate in _iter_candidates(lowered, tenant, source):
        for prefix, upstream in sorted_prefixes:
            if candidate.startswith(prefix):
                return upstream

    wildcard = upstreams.get("*")
    if wildcard:
        return wildcard

    raise ValueError(
        f"Unknown tenant/source for {db_type}: db='{db_name}' user='{user_name or ''}'"
    )
