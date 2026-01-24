"""Minimal Trino HTTP client wrapper."""
from __future__ import annotations

from typing import Any

import httpx


# TODO: Expand error handling and streaming once Trino integration is finalized.

def _build_headers(
    extra_credentials: dict[str, str],
    user: str | None,
    catalog: str | None,
    schema: str | None,
) -> list[tuple[str, str]]:
    headers: list[tuple[str, str]] = [("X-Trino-User", user or "langbridge-gateway")]
    if catalog:
        headers.append(("X-Trino-Catalog", catalog))
    if schema:
        headers.append(("X-Trino-Schema", schema))
    for key, value in extra_credentials.items():
        headers.append(("X-Trino-Extra-Credential", f"{key}={value}"))
    return headers


def execute(
    sql: str,
    trino_url: str | None,
    extra_credentials: dict[str, str],
    user: str | None = None,
    catalog: str | None = None,
    schema: str | None = None,
) -> dict[str, Any]:
    """Execute SQL via Trino's HTTP API or return a stub response."""
    if not trino_url:
        return {
            "status": "stub",
            "query": sql,
            "columns": [],
            "data": [],
            "stats": {"note": "TRINO_URL not set"},
        }

    headers = _build_headers(extra_credentials, user, catalog, schema)
    statement_url = trino_url.rstrip("/") + "/v1/statement"

    with httpx.Client(timeout=30.0) as client:
        response = client.post(statement_url, headers=headers, content=sql.encode("utf-8"))
        response.raise_for_status()
        payload = response.json()

        data: list[Any] = payload.get("data", [])
        columns = payload.get("columns", [])
        next_uri = payload.get("nextUri")
        while next_uri:
            page = client.get(next_uri, headers=headers)
            page.raise_for_status()
            page_payload = page.json()
            if "error" in page_payload:
                return {
                    "status": "error",
                    "error": page_payload.get("error"),
                    "query": sql,
                }
            data.extend(page_payload.get("data", []))
            if not columns:
                columns = page_payload.get("columns", [])
            next_uri = page_payload.get("nextUri")

    return {
        "status": "ok",
        "query": sql,
        "columns": columns,
        "data": data,
    }
