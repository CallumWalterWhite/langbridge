import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from mcp.server.fastmcp import Context, FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from langbridge.runtime.hosting.auth import RuntimeAuthPrincipal, RuntimeAuthResolver
from langbridge.runtime.local_config import ConfiguredLocalRuntimeHost
from langbridge.runtime.models.jobs import (
    CreateDatasetPreviewJobRequest,
    CreateSqlJobRequest,
    SqlWorkbenchMode,
)

DEFAULT_MCP_MOUNT_PATH = "/mcp"


def build_runtime_mcp_server(
    *,
    runtime_host: ConfiguredLocalRuntimeHost,
    auth_resolver: RuntimeAuthResolver,
    mount_path: str = DEFAULT_MCP_MOUNT_PATH,
) -> tuple[FastMCP, Any]:
    normalized_mount_path = _normalize_mount_path(mount_path)
    server = FastMCP(
        name="Langbridge Runtime MCP",
        instructions=(
            "Use these tools to inspect and query the configured Langbridge runtime. "
            "Tool calls execute against the runtime workspace available to the current caller."
        ),
        streamable_http_path="/",
    )

    async def resolve_runtime_host(context: Context) -> ConfiguredLocalRuntimeHost:
        request = _require_request(context)
        principal = _resolve_principal(request=request, auth_resolver=auth_resolver)
        return runtime_host.with_context(
            auth_resolver.build_context(
                request=request,
                principal=principal,
            )
        )

    @server.tool(name="runtime_info")
    async def runtime_info(context: Context) -> dict[str, Any]:
        """Return runtime metadata, enabled capabilities, and the MCP endpoint path."""
        configured_host = await resolve_runtime_host(context)
        connector_items = await configured_host.list_connectors()
        capabilities = _build_runtime_capabilities(
            connector_items=connector_items,
            features=("mcp",),
        )
        return _to_jsonable(
            {
                "runtime_mode": "configured_local",
                "config_path": str(configured_host._config_path),
                "workspace_id": configured_host.context.workspace_id,
                "actor_id": configured_host.context.actor_id,
                "roles": list(configured_host.context.roles),
                "default_semantic_model": configured_host._default_semantic_model_name,
                "default_agent": (
                    configured_host._default_agent.config.name if configured_host._default_agent else None
                ),
                "capabilities": capabilities,
                "mcp_endpoint": normalized_mount_path,
            }
        )

    @server.tool(name="list_datasets")
    async def list_datasets(search: str | None = None, context: Context = None) -> dict[str, Any]:
        """List datasets visible to the current runtime workspace."""
        configured_host = await resolve_runtime_host(context)
        items = await configured_host.list_datasets()
        normalized_search = str(search or "").strip().lower()
        if normalized_search:
            items = [
                item
                for item in items
                if normalized_search in str(item.get("name") or "").lower()
                or normalized_search in str(item.get("description") or "").lower()
            ]
        return _to_jsonable(
            {
                "items": items,
                "total": len(items),
            }
        )

    @server.tool(name="preview_dataset")
    async def preview_dataset(
        dataset: str,
        limit: int = 10,
        context: Context = None,
    ) -> dict[str, Any]:
        """Preview rows from a dataset by name or UUID."""
        configured_host = await resolve_runtime_host(context)
        dataset_id = await _resolve_dataset_id(configured_host, dataset)
        try:
            payload = await configured_host.query_dataset(
                request=CreateDatasetPreviewJobRequest(
                    dataset_id=dataset_id,
                    workspace_id=configured_host.context.workspace_id,
                    actor_id=configured_host.context.actor_id,
                    requested_limit=limit,
                    enforced_limit=limit or 100,
                    correlation_id=configured_host.context.request_id,
                )
            )
        except Exception as exc:
            return {
                "dataset_id": str(dataset_id),
                "status": "failed",
                "error": str(exc),
            }
        return _to_jsonable(
            {
                "dataset_id": dataset_id,
                "dataset_name": payload.get("dataset_name"),
                "status": "succeeded",
                "columns": list(payload.get("columns", [])),
                "rows": list(payload.get("rows", [])),
                "row_count_preview": int(payload.get("row_count_preview") or 0),
                "effective_limit": payload.get("effective_limit"),
                "redaction_applied": bool(payload.get("redaction_applied")),
                "duration_ms": payload.get("duration_ms"),
                "bytes_scanned": payload.get("bytes_scanned"),
                "generated_sql": payload.get("generated_sql"),
            }
        )

    @server.tool(name="query_semantic")
    async def query_semantic(
        semantic_models: list[str] | None = None,
        measures: list[str] | None = None,
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        limit: int | None = None,
        order: dict[str, str] | None = None,
        context: Context = None,
    ) -> dict[str, Any]:
        """Run a semantic query against one or more semantic models."""
        configured_host = await resolve_runtime_host(context)
        selected_models = [item for item in (semantic_models or []) if str(item).strip()]
        if not selected_models:
            default_model = str(configured_host._default_semantic_model_name or "").strip()
            if default_model:
                selected_models = [default_model]
        if not selected_models:
            raise ValueError("semantic_models is required when the runtime does not define a default semantic model.")
        try:
            payload = await configured_host.query_semantic_models(
                semantic_models=selected_models,
                measures=list(measures or []),
                dimensions=list(dimensions or []),
                filters=list(filters or []),
                time_dimensions=[],
                limit=limit,
                order=order,
            )
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
            }
        return _to_jsonable(
            {
                "status": "succeeded",
                "semantic_model_id": payload.get("semantic_model_id"),
                "semantic_model_ids": list(payload.get("semantic_model_ids", [])),
                "connector_id": payload.get("connector_id"),
                "data": list(payload.get("rows", [])),
                "annotations": list(payload.get("annotations", [])),
                "metadata": payload.get("metadata"),
                "generated_sql": payload.get("generated_sql"),
            }
        )

    @server.tool(name="query_sql")
    async def query_sql(
        query: str,
        connection_name: str | None = None,
        selected_datasets: list[dict[str, Any]] | None = None,
        requested_limit: int | None = None,
        requested_timeout_seconds: int | None = None,
        explain: bool = False,
        context: Context = None,
    ) -> dict[str, Any]:
        """Run direct SQL or federated SQL against the runtime."""
        configured_host = await resolve_runtime_host(context)
        normalized_datasets = list(selected_datasets or [])
        if not normalized_datasets and connection_name:
            try:
                payload = await configured_host.execute_sql_text(
                    query=query,
                    connection_name=connection_name,
                    requested_limit=requested_limit,
                )
            except Exception as exc:
                return {
                    "sql_job_id": str(uuid.uuid4()),
                    "status": "failed",
                    "error": {"message": str(exc)},
                    "query": query,
                }
            return _to_jsonable(
                {
                    "sql_job_id": uuid.uuid4(),
                    "status": "succeeded",
                    "columns": list(payload.get("columns", [])),
                    "rows": list(payload.get("rows", [])),
                    "row_count_preview": int(payload.get("row_count_preview") or 0),
                    "total_rows_estimate": payload.get("total_rows_estimate"),
                    "bytes_scanned": payload.get("bytes_scanned"),
                    "duration_ms": payload.get("duration_ms"),
                    "redaction_applied": bool(payload.get("redaction_applied")),
                    "query": query,
                    "generated_sql": payload.get("generated_sql"),
                }
            )

        sql_job_id = uuid.uuid4()
        create_request = CreateSqlJobRequest(
            sql_job_id=sql_job_id,
            workspace_id=configured_host.context.workspace_id,
            actor_id=configured_host.context.actor_id,
            workbench_mode=(
                SqlWorkbenchMode.dataset if normalized_datasets else SqlWorkbenchMode.direct_sql
            ),
            connection_id=None,
            execution_mode=("federated" if normalized_datasets else "single"),
            query=query,
            query_dialect="tsql",
            params={},
            requested_limit=requested_limit,
            requested_timeout_seconds=requested_timeout_seconds,
            enforced_limit=requested_limit or 100,
            enforced_timeout_seconds=requested_timeout_seconds or 30,
            allow_dml=False,
            allow_federation=bool(normalized_datasets),
            selected_datasets=normalized_datasets,
            federated_datasets=normalized_datasets,
            explain=bool(explain),
            correlation_id=configured_host.context.request_id,
        )
        try:
            payload = await configured_host.execute_sql(request=create_request)
        except Exception as exc:
            return {
                "sql_job_id": str(sql_job_id),
                "status": "failed",
                "error": {"message": str(exc)},
                "query": query,
            }
        return _to_jsonable(
            {
                "sql_job_id": sql_job_id,
                "status": "succeeded",
                "columns": list(payload.get("columns", [])),
                "rows": list(payload.get("rows", [])),
                "row_count_preview": int(payload.get("row_count_preview") or 0),
                "total_rows_estimate": payload.get("total_rows_estimate"),
                "bytes_scanned": payload.get("bytes_scanned"),
                "duration_ms": payload.get("duration_ms"),
                "redaction_applied": bool(payload.get("redaction_applied")),
                "query": query,
                "generated_sql": payload.get("generated_sql"),
            }
        )

    @server.tool(name="ask_agent")
    async def ask_agent(
        message: str,
        agent_name: str | None = None,
        context: Context = None,
    ) -> dict[str, Any]:
        """Ask the default runtime agent, or a named agent, a grounded analytics question."""
        configured_host = await resolve_runtime_host(context)
        try:
            payload = await configured_host.ask_agent(
                prompt=message,
                agent_name=str(agent_name or "").strip() or None,
            )
        except Exception as exc:
            return {
                "status": "failed",
                "error": {"message": str(exc)},
            }
        return _to_jsonable(
            {
                "status": "succeeded",
                "thread_id": payload.get("thread_id"),
                "job_id": payload.get("job_id"),
                "summary": payload.get("summary"),
                "result": payload.get("result"),
                "visualization": payload.get("visualization"),
                "error": payload.get("error"),
                "events": list(payload.get("events", [])),
            }
        )

    mounted_app = _RuntimeMCPAuthMiddleware(
        app=server.streamable_http_app(),
        auth_resolver=auth_resolver,
    )
    return server, mounted_app


class _RuntimeMCPAuthMiddleware:
    def __init__(self, *, app: Any, auth_resolver: RuntimeAuthResolver) -> None:
        self._app = app
        self._auth_resolver = auth_resolver

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        try:
            principal = await self._auth_resolver.authenticate(request)
        except HTTPException as exc:
            response = JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
            )
            await response(scope, receive, send)
            return

        scope.setdefault("state", {})
        scope["state"]["runtime_principal"] = principal
        await self._app(scope, receive, send)


def _require_request(context: Context) -> Request:
    request = context.request_context.request
    if not isinstance(request, Request):
        raise RuntimeError("Langbridge MCP tools require an HTTP request context.")
    return request


def _resolve_principal(
    *,
    request: Request,
    auth_resolver: RuntimeAuthResolver,
) -> RuntimeAuthPrincipal:
    principal = getattr(request.state, "runtime_principal", None)
    if isinstance(principal, RuntimeAuthPrincipal):
        return principal
    raise RuntimeError("Langbridge MCP request authentication context is missing.")


async def _resolve_dataset_id(
    runtime_host: ConfiguredLocalRuntimeHost,
    dataset_ref: str,
) -> uuid.UUID:
    normalized_ref = str(dataset_ref or "").strip()
    if not normalized_ref:
        raise ValueError("dataset is required.")
    try:
        return uuid.UUID(normalized_ref)
    except ValueError:
        pass

    datasets = await runtime_host.list_datasets()
    for item in datasets:
        if str(item.get("name") or "").strip() != normalized_ref:
            continue
        item_id = item.get("id")
        if item_id is None:
            break
        try:
            return uuid.UUID(str(item_id))
        except (TypeError, ValueError):
            break
    raise ValueError(f"Dataset '{dataset_ref}' was not found.")


def _build_runtime_capabilities(
    *,
    connector_items: Sequence[dict[str, Any]],
    features: Sequence[str],
) -> list[str]:
    capabilities = [
        "datasets.list",
        "datasets.preview",
        "semantic.query",
        "sql.query",
        "agents.ask",
    ]
    if connector_items:
        capabilities.append("connectors.list")
    if any(bool(item.get("supports_sync")) for item in connector_items):
        capabilities.extend(
            [
                "sync.resources",
                "sync.states",
                "sync.run",
            ]
        )
    for feature in features:
        normalized = str(feature or "").strip().lower()
        if normalized and normalized not in capabilities:
            capabilities.append(normalized)
    return capabilities


def _normalize_mount_path(value: str) -> str:
    normalized = "/" + str(value or "").strip().strip("/")
    return "/" if normalized == "//" else normalized


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump(mode="json"))
    return value
