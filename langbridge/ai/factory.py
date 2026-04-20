"""Factory for constructing the Langbridge AI runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from langbridge.ai.agents.analyst import AnalystAgent
from langbridge.ai.agents.presentation import PresentationAgent
from langbridge.ai.base import BaseAgent
from langbridge.ai.llm.base import LLMProvider
from langbridge.ai.meta_controller import MetaControllerAgent
from langbridge.ai.profiles import AgentProfile, AgentProfileRegistryBuilder, AnalystAgentScope
from langbridge.ai.registry import AgentRegistry
from langbridge.ai.tools.charting import ChartingTool
from langbridge.ai.tools.semantic_search import SemanticSearchTool
from langbridge.ai.tools.sql import SqlAnalysisTool
from langbridge.ai.tools.web_search import (
    WebSearchPolicy,
    WebSearchProvider,
    WebSearchTool,
    create_web_search_provider,
)


@dataclass(slots=True)
class AnalystToolBundle:
    scope: AnalystAgentScope
    sql_tools: Sequence[SqlAnalysisTool] = field(default_factory=list)
    semantic_search_tools: Sequence[SemanticSearchTool] = field(default_factory=list)
    web_search_provider: WebSearchProvider | None = None


class LangbridgeAIFactory:
    """Owns AI runtime construction so host/runtime code does not wire agents manually."""

    def __init__(self, *, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    def create_meta_controller(
        self,
        *,
        analysts: Sequence[AnalystToolBundle],
        extra_agents: Sequence[BaseAgent] | None = None,
        max_iterations: int = 8,
        max_replans: int = 2,
        max_step_retries: int = 1,
    ) -> MetaControllerAgent:
        agents: list[BaseAgent] = [
            AnalystAgent(
                llm_provider=self._llm,
                scope=bundle.scope,
                sql_analysis_tools=bundle.sql_tools,
                semantic_search_tools=bundle.semantic_search_tools,
                web_search_tool=self._web_tool_for(bundle),
            )
            for bundle in analysts
        ]
        agents.extend(extra_agents or [])
        return MetaControllerAgent(
            registry=AgentRegistry(agents),
            presentation_agent=PresentationAgent(
                llm_provider=self._llm,
                charting_tool=ChartingTool(llm_provider=self._llm),
            ),
            max_iterations=max_iterations,
            max_replans=max_replans,
            max_step_retries=max_step_retries,
        )

    def create_profile_runtime(
        self,
        profile: AgentProfile,
        *,
        sql_analysis_tools: Mapping[str, list[SqlAnalysisTool]] | None = None,
        semantic_search_tools: Mapping[str, list[SemanticSearchTool]] | None = None,
        web_search_providers: Mapping[str, WebSearchProvider] | None = None,
    ) -> Any:
        return AgentProfileRegistryBuilder().build_runtime(
            profile,
            llm_provider=self._llm,
            sql_analysis_tools=sql_analysis_tools,
            semantic_search_tools=semantic_search_tools,
            web_search_providers=web_search_providers,
        )

    @staticmethod
    def _web_tool_for(bundle: AnalystToolBundle) -> WebSearchTool | None:
        scope = bundle.scope
        if not scope.web_search_enabled:
            return None
        provider = bundle.web_search_provider or create_web_search_provider(scope.web_search_provider)
        return WebSearchTool(
            provider=provider,
            policy=WebSearchPolicy(
                allowed_domains=list(scope.web_search_allowed_domains),
                denied_domains=list(scope.web_search_denied_domains),
                require_allowed_domain=scope.web_search_require_allowed_domain,
                focus_terms=list(scope.web_search_focus_terms),
                max_results=scope.web_search_max_results,
                region=scope.web_search_region,
                safe_search=scope.web_search_safe_search,
                timebox_seconds=scope.web_search_timebox_seconds,
            ),
        )


__all__ = ["AnalystToolBundle", "LangbridgeAIFactory"]
