from __future__ import annotations

from typing import Any

import httpx


class InternalApiClient:
    """HTTP client for calling Langbridge API with the internal service token."""

    def __init__(
        self,
        base_url: str,
        service_token: str,
        timeout: float = 30.0,
    ) -> None:
        if not service_token:
            raise ValueError("SERVICE_USER_SECRET is required for internal API client")
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._timeout = timeout

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base_url}{path}"

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["x-langbridge-service-token"] = self._service_token
        url = self._build_url(path)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.request(method, url, headers=headers, **kwargs)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)
