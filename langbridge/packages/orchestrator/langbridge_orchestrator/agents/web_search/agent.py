"""
Web search agent that retrieves and normalizes search results.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Protocol
from urllib.parse import urlparse

import httpx

from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider import LLMProvider

DEFAULT_MAX_RESULTS = 6
MAX_RESULTS_CAP = 20


@dataclass
class WebSearchResultItem:
    """Single web search result."""

    title: str
    url: str
    snippet: str = ""
    source: str = ""
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "rank": self.rank,
        }

    def to_row(self) -> list[str]:
        return [
            str(self.rank) if self.rank else "",
            self.title,
            self.url,
            self.snippet,
            self.source,
        ]


@dataclass
class WebSearchResult:
    """Aggregated web search output."""

    query: str
    provider: str
    results: list[WebSearchResultItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "provider": self.provider,
            "results": [result.to_dict() for result in self.results],
            "warnings": list(self.warnings),
        }

    def to_tabular(self) -> Dict[str, Any]:
        if not self.results:
            return {
                "columns": ["message"],
                "rows": [[f"No web results found for '{self.query}'."]],
            }

        return {
            "columns": ["rank", "title", "url", "snippet", "source"],
            "rows": [result.to_row() for result in self.results],
        }

    def to_documents(self) -> list[Dict[str, Any]]:
        return [
            {
                "title": result.title,
                "snippet": result.snippet,
                "url": result.url,
                "source": result.source,
            }
            for result in self.results
        ]


class WebSearchProvider(Protocol):
    """Protocol describing a web search provider implementation."""

    name: str

    def search(
        self,
        query: str,
        *,
        max_results: int,
        region: Optional[str],
        safe_search: Optional[str],
        timebox_seconds: int,
    ) -> list[WebSearchResultItem]:
        ...

    async def search_async(
        self,
        query: str,
        *,
        max_results: int,
        region: Optional[str],
        safe_search: Optional[str],
        timebox_seconds: int,
    ) -> list[WebSearchResultItem]:
        ...


class DuckDuckGoInstantAnswerProvider:
    """DuckDuckGo Instant Answer API provider."""

    name = "duckduckgo"

    _SAFE_SEARCH_MAP = {
        "off": "-1",
        "moderate": "1",
        "strict": "2",
    }

    def __init__(
        self,
        *,
        base_url: str = "https://api.duckduckgo.com/",
        user_agent: str = "langbridge-web-search/1.0",
    ) -> None:
        self.base_url = base_url
        self.user_agent = user_agent

    def search(
        self,
        query: str,
        *,
        max_results: int,
        region: Optional[str],
        safe_search: Optional[str],
        timebox_seconds: int,
    ) -> list[WebSearchResultItem]:
        params = self._build_params(query, region=region, safe_search=safe_search)
        timeout = httpx.Timeout(timebox_seconds)
        with httpx.Client(timeout=timeout, headers={"User-Agent": self.user_agent}) as client:
            response = client.get(self.base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        return self._parse_results(query, payload, max_results=max_results)

    async def search_async(
        self,
        query: str,
        *,
        max_results: int,
        region: Optional[str],
        safe_search: Optional[str],
        timebox_seconds: int,
    ) -> list[WebSearchResultItem]:
        params = self._build_params(query, region=region, safe_search=safe_search)
        timeout = httpx.Timeout(timebox_seconds)
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": self.user_agent}) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        return self._parse_results(query, payload, max_results=max_results)

    def _build_params(
        self,
        query: str,
        *,
        region: Optional[str],
        safe_search: Optional[str],
    ) -> Dict[str, str]:
        params = {
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "t": "langbridge",
        }
        if region:
            params["kl"] = region
        safe_value = self._normalize_safe_search(safe_search)
        if safe_value is not None:
            params["kp"] = safe_value
        return params

    def _parse_results(
        self,
        query: str,
        payload: Dict[str, Any],
        *,
        max_results: int,
    ) -> list[WebSearchResultItem]:
        results: list[WebSearchResultItem] = []
        seen_urls: set[str] = set()

        def _add_result(title: str, url: str, snippet: str, source: Optional[str] = None) -> None:
            if not url or url in seen_urls:
                return
            seen_urls.add(url)
            clean_title = (title or url).strip()
            clean_snippet = (snippet or "").strip()
            resolved_source = (source or self._source_from_url(url) or self.name).strip()
            results.append(
                WebSearchResultItem(
                    title=clean_title,
                    url=url,
                    snippet=clean_snippet,
                    source=resolved_source,
                )
            )

        heading = str(payload.get("Heading") or "").strip()
        abstract_text = str(payload.get("AbstractText") or payload.get("Abstract") or "").strip()
        abstract_url = str(payload.get("AbstractURL") or "").strip()
        abstract_source = str(payload.get("AbstractSource") or "").strip()
        if abstract_text and abstract_url:
            _add_result(heading or abstract_source or query, abstract_url, abstract_text, abstract_source)

        answer = str(payload.get("Answer") or "").strip()
        answer_url = str(payload.get("AnswerURL") or "").strip()
        answer_type = str(payload.get("AnswerType") or "").strip()
        if answer and answer_url:
            _add_result(heading or answer_type or query, answer_url, answer, answer_type)

        definition = str(payload.get("Definition") or "").strip()
        definition_url = str(payload.get("DefinitionURL") or "").strip()
        definition_source = str(payload.get("DefinitionSource") or "").strip()
        if definition and definition_url:
            _add_result(heading or definition_source or query, definition_url, definition, definition_source)

        for entry in self._iter_related_topics(payload.get("RelatedTopics")):
            if len(results) >= max_results:
                break
            text = str(entry.get("Text") or "").strip()
            url = str(entry.get("FirstURL") or "").strip()
            if not text or not url:
                continue
            title = text.split(" - ", 1)[0].strip() if " - " in text else text
            _add_result(title or query, url, text, None)

        if len(results) < max_results:
            for entry in self._coerce_list(payload.get("Results")):
                if len(results) >= max_results:
                    break
                text = str(entry.get("Text") or "").strip()
                url = str(entry.get("FirstURL") or "").strip()
                if not text or not url:
                    continue
                title = text.split(" - ", 1)[0].strip() if " - " in text else text
                _add_result(title or query, url, text, None)

        return results[:max_results]

    @staticmethod
    def _iter_related_topics(raw_topics: Any) -> Iterable[Dict[str, Any]]:
        for topic in DuckDuckGoInstantAnswerProvider._coerce_list(raw_topics):
            if "Topics" in topic:
                for nested in DuckDuckGoInstantAnswerProvider._coerce_list(topic.get("Topics")):
                    yield nested
                continue
            if isinstance(topic, dict):
                yield topic

    @staticmethod
    def _coerce_list(value: Any) -> list[Dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _source_from_url(url: str) -> str:
        try:
            return urlparse(url).netloc
        except ValueError:
            return ""

    @classmethod
    def _normalize_safe_search(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        lowered = value.strip().lower()
        return cls._SAFE_SEARCH_MAP.get(lowered)


class WebSearchAgent:
    """Agent that delegates to a web search provider."""

    def __init__(
        self,
        *,
        provider: Optional[WebSearchProvider] = None,
        llm: Optional[LLMProvider] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.provider = provider or DuckDuckGoInstantAnswerProvider()
        self.logger = logger or logging.getLogger(__name__)
        self.llm = llm

    @staticmethod
    def _extract_json_blob(text: str) -> Optional[str]:
        if not text:
            return None
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    def _parse_llm_payload(self, response: str) -> Optional[Dict[str, Any]]:
        blob = self._extract_json_blob(response)
        if not blob:
            return None
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    @staticmethod
    def _normalize_alternates(value: Any, base_query: str) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if not text or text == base_query:
                continue
            cleaned.append(text)
        return cleaned

    @staticmethod
    def _dedupe_queries(queries: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for query in queries:
            if not query:
                continue
            if query in seen:
                continue
            seen.add(query)
            ordered.append(query)
        return ordered

    def _build_llm_prompt(self, query: str) -> str:
        prompt_sections = [
            "You are a web search assistant. Rewrite the query to maximize relevant results.",
            "Return ONLY JSON with keys: query, alternates.",
            "query must be a concise search string. alternates is a list of backup queries.",
            f"Original query: {query}",
        ]
        return "\n".join(prompt_sections)

    def _rewrite_query_with_llm(self, query: str) -> Optional[Dict[str, Any]]:
        if not self.llm:
            return None
        prompt = self._build_llm_prompt(query)
        try:
            response = self.llm.complete(prompt, temperature=0.0, max_tokens=160)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("WebSearchAgent LLM query rewrite failed: %s", exc)
            return None
        payload = self._parse_llm_payload(str(response))
        if not payload:
            return None
        return payload

    async def _rewrite_query_with_llm_async(self, query: str) -> Optional[Dict[str, Any]]:
        if not self.llm:
            return None
        return await asyncio.to_thread(self._rewrite_query_with_llm, query)

    def _prepare_query_candidates(self, query: str) -> tuple[str, list[str], list[str]]:
        warnings: list[str] = []
        payload = self._rewrite_query_with_llm(query)
        if not payload:
            return query, [], warnings
        llm_query = str(payload.get("query") or payload.get("search_query") or "").strip()
        if llm_query and llm_query != query:
            warnings.append(f"LLM rewrote query to '{llm_query}'.")
        alternates = self._normalize_alternates(
            payload.get("alternates") or payload.get("alternate_queries") or payload.get("queries"),
            llm_query or query,
        )
        return llm_query or query, alternates, warnings

    async def _prepare_query_candidates_async(self, query: str) -> tuple[str, list[str], list[str]]:
        warnings: list[str] = []
        payload = await self._rewrite_query_with_llm_async(query)
        if not payload:
            return query, [], warnings
        llm_query = str(payload.get("query") or payload.get("search_query") or "").strip()
        if llm_query and llm_query != query:
            warnings.append(f"LLM rewrote query to '{llm_query}'.")
        alternates = self._normalize_alternates(
            payload.get("alternates") or payload.get("alternate_queries") or payload.get("queries"),
            llm_query or query,
        )
        return llm_query or query, alternates, warnings

    def _execute_query_sequence(
        self,
        queries: list[str],
        *,
        max_results: int,
        region: Optional[str],
        safe_search: Optional[str],
        timebox_seconds: int,
    ) -> tuple[list[WebSearchResultItem], str, list[str]]:
        attempts: list[str] = []
        for candidate in queries:
            attempts.append(candidate)
            results = self.provider.search(
                candidate,
                max_results=max_results,
                region=region,
                safe_search=safe_search,
                timebox_seconds=timebox_seconds,
            )
            if results:
                return results, candidate, attempts
        return [], attempts[-1] if attempts else "", attempts

    async def _execute_query_sequence_async(
        self,
        queries: list[str],
        *,
        max_results: int,
        region: Optional[str],
        safe_search: Optional[str],
        timebox_seconds: int,
    ) -> tuple[list[WebSearchResultItem], str, list[str]]:
        attempts: list[str] = []
        for candidate in queries:
            attempts.append(candidate)
            results = await self.provider.search_async(
                candidate,
                max_results=max_results,
                region=region,
                safe_search=safe_search,
                timebox_seconds=timebox_seconds,
            )
            if results:
                return results, candidate, attempts
        return [], attempts[-1] if attempts else "", attempts

    def search(
        self,
        query: str,
        *,
        max_results: int = DEFAULT_MAX_RESULTS,
        region: Optional[str] = None,
        safe_search: Optional[str] = None,
        timebox_seconds: int = 10,
    ) -> WebSearchResult:
        clean_query = self._normalize_query(query)
        capped_max_results = self._normalize_max_results(max_results)
        primary_query, alternates, warnings = self._prepare_query_candidates(clean_query)
        query_sequence = self._dedupe_queries([primary_query, *alternates, clean_query])
        results, final_query, attempts = self._execute_query_sequence(
            query_sequence,
            max_results=capped_max_results,
            region=region,
            safe_search=safe_search,
            timebox_seconds=timebox_seconds,
        )
        if final_query and final_query != clean_query:
            warnings.append(f"Search used query '{final_query}' after {len(attempts)} attempt(s).")
        if not results:
            warnings.append("No web results returned by the provider.")
        self._apply_ranking(results)
        self.logger.info(
            "WebSearchAgent retrieved %d result(s) for query '%s' via %s",
            len(results),
            final_query or clean_query,
            self.provider.name,
        )
        return WebSearchResult(
            query=final_query or clean_query,
            provider=self.provider.name,
            results=results,
            warnings=warnings,
        )

    async def search_async(
        self,
        query: str,
        *,
        max_results: int = DEFAULT_MAX_RESULTS,
        region: Optional[str] = None,
        safe_search: Optional[str] = None,
        timebox_seconds: int = 10,
    ) -> WebSearchResult:
        clean_query = self._normalize_query(query)
        capped_max_results = self._normalize_max_results(max_results)
        primary_query, alternates, warnings = await self._prepare_query_candidates_async(clean_query)
        query_sequence = self._dedupe_queries([primary_query, *alternates, clean_query])
        results, final_query, attempts = await self._execute_query_sequence_async(
            query_sequence,
            max_results=capped_max_results,
            region=region,
            safe_search=safe_search,
            timebox_seconds=timebox_seconds,
        )
        if final_query and final_query != clean_query:
            warnings.append(f"Search used query '{final_query}' after {len(attempts)} attempt(s).")
        if not results:
            warnings.append("No web results returned by the provider.")
        self._apply_ranking(results)
        self.logger.info(
            "WebSearchAgent retrieved %d result(s) for query '%s' via %s",
            len(results),
            final_query or clean_query,
            self.provider.name,
        )
        return WebSearchResult(
            query=final_query or clean_query,
            provider=self.provider.name,
            results=results,
            warnings=warnings,
        )

    @staticmethod
    def _normalize_query(query: str) -> str:
        clean = str(query or "").strip()
        if not clean:
            raise ValueError("WebSearchAgent requires a non-empty query.")
        return clean

    @staticmethod
    def _normalize_max_results(max_results: int) -> int:
        if max_results < 1:
            raise ValueError("max_results must be at least 1.")
        return min(int(max_results), MAX_RESULTS_CAP)

    @staticmethod
    def _apply_ranking(results: list[WebSearchResultItem]) -> None:
        for idx, result in enumerate(results, start=1):
            result.rank = idx


__all__ = [
    "DuckDuckGoInstantAnswerProvider",
    "WebSearchAgent",
    "WebSearchProvider",
    "WebSearchResult",
    "WebSearchResultItem",
]
