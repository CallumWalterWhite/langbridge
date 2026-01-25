"""HTTP gateway for SQL execution via Trino."""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import Response

from langbridge.packages.common.langbridge_common.monitoring import (
    PrometheusMiddleware,
    metrics_response,
)

from .auth.secrets_provider import get_db_credentials
from .trino_client.client import execute


class QueryRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    source_id: str | None = None
    session: dict[str, str] | None = None
    user: str | None = None
    catalog: str | None = None
    schema: str | None = None


class QueryResponse(BaseModel):
    status: str
    query: str
    columns: list[dict[str, Any]] | list[Any]
    data: list[Any]
    stats: dict[str, Any] | None = None


app = FastAPI(title="Langbridge Gateway", version="0.1.0")
app.add_middleware(PrometheusMiddleware, service_name="langbridge_gateway")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    credentials = get_db_credentials(request.tenant_id, request.source_id)
    # TODO: Apply request.session to Trino session headers when implemented.
    extra_credentials = credentials.get("extra_credentials", {})
    user = request.user or credentials.get("user")
    catalog = request.catalog or credentials.get("catalog")
    schema = request.schema or credentials.get("schema")
    trino_url = os.environ.get("TRINO_URL")

    try:
        result = execute(
            sql=request.sql,
            trino_url=trino_url,
            extra_credentials=extra_credentials,
            user=user,
            catalog=catalog,
            schema=schema,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gateway execution failed: {exc}") from exc

    return QueryResponse(
        status=result.get("status", "unknown"),
        query=result.get("query", request.sql),
        columns=result.get("columns", []),
        data=result.get("data", []),
        stats=result.get("stats"),
    )


@app.get("/metrics")
def metrics() -> Response:
    return metrics_response()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("GATEWAY_PORT", "8001"))
    uvicorn.run(
        "langbridge.apps.gateway.langbridge_gateway.main:app",
        host="0.0.0.0",
        port=port,
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
        reload=bool(os.environ.get("UVICORN_RELOAD")),
    )
