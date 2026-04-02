from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

import httpx

from .errors import (
    AuthError,
    ConnectorError,
)

from .connector import ApiConnector, ApiExtractResult, ApiResource, ApiSyncResult


@dataclass(frozen=True, slots=True)
class ApiResourceDefinition:
    resource: ApiResource
    path: str
    response_key: str | None = None
    request_params: Mapping[str, Any] | None = None


class HttpApiConnector(ApiConnector):
    RESOURCE_DEFINITIONS: Mapping[str, ApiResourceDefinition] = {}

    def __init__(
        self,
        config: Any,
        logger=None,
        *,
        transport: Any | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        super().__init__(config=config, logger=logger)
        self._transport = transport
        self._timeout_s = timeout_s

    async def discover_resources(self) -> list[ApiResource]:
        return [definition.resource for definition in self.RESOURCE_DEFINITIONS.values()]

    async def sync_resource(
        self,
        resource_name: str,
        *,
        since: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ApiSyncResult:
        result = await self.extract_resource(
            resource_name,
            since=since,
            cursor=cursor,
            limit=limit,
        )
        return ApiSyncResult(
            resource=resource_name,
            status=result.status,
            records_synced=len(result.records),
            datasets_created=[],
        )

    def _require_resource(self, resource_name: str) -> ApiResourceDefinition:
        definition = self.RESOURCE_DEFINITIONS.get(resource_name)
        if definition is None:
            raise ConnectorError(f"Unsupported resource '{resource_name}'.")
        return definition

    @staticmethod
    def _clamp_limit(limit: int | None, *, default: int, maximum: int) -> int:
        if limit is None:
            return default
        return max(1, min(int(limit), maximum))

    async def _request(
        self,
        method: str,
        path_or_url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_payload: Any | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        url = self._resolve_url(path_or_url)
        request_headers = {
            "Accept": "application/json",
            **self._default_headers(),
            **dict(headers or {}),
        }
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(self._timeout_s),
                follow_redirects=True
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_payload,
                    data=data,
                )
        except httpx.RequestError as exc:
            raise ConnectorError(f"Request to {url} failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise AuthError(self._error_message(response, fallback=f"Authentication failed for {url}."))
        if response.status_code >= 400:
            raise ConnectorError(
                self._error_message(
                    response,
                    fallback=f"Request to {url} failed with status {response.status_code}.",
                )
            )
        return response

    async def _request_json(
        self,
        method: str,
        path_or_url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_payload: Any | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> tuple[Any, httpx.Response]:
        response = await self._request(
            method,
            path_or_url,
            headers=headers,
            params=params,
            json_payload=json_payload,
            data=data,
        )
        try:
            return response.json(), response
        except ValueError as exc:
            raise ConnectorError(f"Response from {response.request.url} was not valid JSON.") from exc

    def _resolve_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        base_url = self._base_url().rstrip("/")
        path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"
        return f"{base_url}{path}"

    def _base_url(self) -> str:
        raise NotImplementedError

    def _default_headers(self) -> dict[str, str]:
        return {}

    @staticmethod
    def _error_message(response: httpx.Response, *, fallback: str) -> str:
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text or fallback

        if isinstance(payload, dict):
            for key in ("error_description", "error", "message"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            if isinstance(payload.get("errors"), list) and payload["errors"]:
                first = payload["errors"][0]
                if isinstance(first, str) and first.strip():
                    return first.strip()
                if isinstance(first, dict):
                    for key in ("message", "detail", "code"):
                        value = first.get(key)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
        return fallback


def parse_link_header_cursor(link_header: str | None, *, param_name: str = "page_info") -> str | None:
    if not link_header:
        return None

    for fragment in link_header.split(","):
        if 'rel="next"' not in fragment:
            continue
        start = fragment.find("<")
        end = fragment.find(">", start + 1)
        if start == -1 or end == -1:
            continue
        next_url = fragment[start + 1 : end]
        parsed = parse_qs(urlparse(next_url).query)
        values = parsed.get(param_name)
        if values:
            return values[0]
    return None
