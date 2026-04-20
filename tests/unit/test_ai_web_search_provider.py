import asyncio

import httpx

from langbridge.ai.profiles import AgentProfile, AgentProfileRegistryBuilder
from langbridge.ai.tools.web_search import (
    DuckDuckGoWebSearchProvider,
    create_web_search_provider,
)


def _run(coro):
    return asyncio.run(coro)


def test_duckduckgo_provider_parses_json_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.duckduckgo.com"
        return httpx.Response(
            200,
            json={
                "Heading": "Langbridge",
                "AbstractText": "Langbridge runtime docs.",
                "AbstractURL": "https://docs.langbridge.dev/runtime",
                "AbstractSource": "Langbridge Docs",
                "RelatedTopics": [
                    {
                        "Text": "Langbridge semantic layer - Semantic docs.",
                        "FirstURL": "https://docs.langbridge.dev/semantic",
                    }
                ],
            },
            request=request,
        )

    provider = DuckDuckGoWebSearchProvider(transport=httpx.MockTransport(handler))

    results = _run(provider.search_async("langbridge runtime", max_results=5))

    assert [item.url for item in results] == [
        "https://docs.langbridge.dev/runtime",
        "https://docs.langbridge.dev/semantic",
    ]
    assert results[0].source == "Langbridge Docs"
    assert results[0].rank == 1
    assert results[1].rank == 2


def test_duckduckgo_provider_uses_html_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.duckduckgo.com":
            return httpx.Response(200, json={}, request=request)
        assert request.url.host == "lite.duckduckgo.com"
        return httpx.Response(
            200,
            text="""
            <a class="result-link" href="/l/?uddg=https%3A%2F%2Fdocs.langbridge.dev%2Fruntime">
              Langbridge runtime
            </a>
            <td class="result-snippet">Runtime docs for Langbridge.</td>
            """,
            request=request,
        )

    provider = DuckDuckGoWebSearchProvider(transport=httpx.MockTransport(handler))

    results = _run(provider.search_async("langbridge runtime", max_results=1))

    assert len(results) == 1
    assert results[0].url == "https://docs.langbridge.dev/runtime"
    assert results[0].title == "Langbridge runtime"
    assert results[0].snippet == "Runtime docs for Langbridge."


def test_create_web_search_provider_rejects_unknown_provider() -> None:
    try:
        create_web_search_provider("unknown")
    except ValueError as exc:
        assert "Unsupported web search provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown provider should fail")


def test_profile_builder_creates_default_web_search_provider_for_enabled_scope() -> None:
    profile = AgentProfile.from_definition(
        name="docs_research",
        definition={
            "features": {"deep_research_enabled": True},
            "tools": [
                {
                    "name": "docs_search",
                    "tool_type": "web_search",
                    "config": {
                        "provider": "duckduckgo",
                        "allowed_domains": ["docs.langbridge.dev"],
                    },
                }
            ],
        },
    )

    registry = AgentProfileRegistryBuilder().build_registry(profile, llm_provider=object())
    agent_name = registry.specifications()[0].name
    analyst = registry.get(agent_name)

    assert any(tool.name == "web-search" for tool in analyst.specification.tools)
