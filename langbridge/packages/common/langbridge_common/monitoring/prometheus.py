from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest, start_http_server


@dataclass(frozen=True)
class HttpMetrics:
    request_count: Counter
    request_latency: Histogram


_HTTP_METRICS: Dict[str, HttpMetrics] = {}


def _http_metrics(service_name: str) -> HttpMetrics:
    metrics = _HTTP_METRICS.get(service_name)
    if metrics is None:
        metrics = HttpMetrics(
            request_count=Counter(
                f"{service_name}_http_requests_total",
                "Total HTTP requests",
                ["method", "path", "status"],
            ),
            request_latency=Histogram(
                f"{service_name}_http_request_latency_seconds",
                "HTTP request latency in seconds",
                ["method", "path"],
            ),
        )
        _HTTP_METRICS[service_name] = metrics
    return metrics


def _resolve_path(request: Any) -> str:
    route = getattr(request, "scope", {}).get("route")
    path = getattr(route, "path", None)
    return path or request.url.path


try:
    from starlette.middleware.base import BaseHTTPMiddleware
except ImportError:  # pragma: no cover - optional dependency for worker-only runtime
    BaseHTTPMiddleware = object  # type: ignore[assignment]


class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, service_name: str) -> None:
        if BaseHTTPMiddleware is object:
            raise ImportError("starlette is required to use PrometheusMiddleware")
        super().__init__(app)
        self._metrics = _http_metrics(service_name)

    async def dispatch(self, request: Any, call_next) -> Any:
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            path = _resolve_path(request)
            duration = time.perf_counter() - start
            self._metrics.request_count.labels(request.method, path, status_code).inc()
            self._metrics.request_latency.labels(request.method, path).observe(duration)


def metrics_response() -> Any:
    from starlette.responses import Response

    payload = generate_latest()
    return Response(payload, media_type=CONTENT_TYPE_LATEST)


def start_metrics_server(port: int, *, addr: str = "0.0.0.0") -> None:
    start_http_server(port, addr=addr)
