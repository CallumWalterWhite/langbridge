"""Profile-scoped registry construction for Langbridge AI agents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel, Field, model_validator

from langbridge.ai.registry import AgentRegistry

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]


def _routing_terms(values: list[str]) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for value in values:
        for token in _TOKEN_RE.findall(value.casefold()):
            if token not in seen:
                seen.add(token)
                terms.append(token)
    return terms


def _config_value(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, Mapping):
        return config.get(key, default)
    return getattr(config, key, default)


def _scoped_agent_name(kind: str, name: str) -> str:
    clean_name = str(name or kind).strip()
    if clean_name == kind or clean_name.startswith(f"{kind}."):
        return clean_name
    return f"{kind}.{clean_name}"


class AgentProfileFeatures(BaseModel):
    bi_copilot_enabled: bool = False
    deep_research_enabled: bool = False
    visualization_enabled: bool = True
    mcp_enabled: bool = False


class AgentProfileExecution(BaseModel):
    mode: str = "iterative"
    response_mode: str = "analyst"
    max_iterations: int = 3
    max_steps_per_iteration: int = 5
    allow_parallel_tools: bool = False


class AgentProfileAccessPolicy(BaseModel):
    allowed_connectors: list[str] = Field(default_factory=list)
    denied_connectors: list[str] = Field(default_factory=list)
    pii_handling: str | None = None
    row_level_filter: str | None = None


class AnalystAgentScope(BaseModel):
    name: str = "analyst"
    description: str | None = None
    enabled_modes: list[str] = Field(default_factory=lambda: ["quick", "semantic", "sql"])
    deep_research_enabled: bool = False
    semantic_model_ids: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    query_scope_policy: str = "semantic_preferred"
    allow_source_scope: bool = False
    allowed_evidence_agents: list[str] = Field(default_factory=list)
    max_sources: int = 8
    require_sources: bool = False
    web_search_enabled: bool = False
    web_search_name: str | None = None
    web_search_provider: str | None = None
    web_search_allowed_domains: list[str] = Field(default_factory=list)
    web_search_denied_domains: list[str] = Field(default_factory=list)
    web_search_require_allowed_domain: bool = False
    web_search_provider_required: bool = False
    web_search_focus_terms: list[str] = Field(default_factory=list)
    web_search_max_results: int = 6
    web_search_region: str | None = None
    web_search_safe_search: str | None = None
    web_search_timebox_seconds: int = 10
    preferred_dataset_id: str | None = None
    preferred_semantic_model_id: str | None = None
    allowed_connectors: list[str] = Field(default_factory=list)
    denied_connectors: list[str] = Field(default_factory=list)
    routing_keywords: list[str] = Field(default_factory=list)
    routing_phrases: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enable_requested_modes(self) -> "AnalystAgentScope":
        modes = list(self.enabled_modes)
        if self.deep_research_enabled:
            modes.extend(["research", "deep_research", "hybrid"])
        if self.web_search_enabled:
            modes.extend(["research", "hybrid"])
        self.enabled_modes = list(dict.fromkeys(modes))
        if self.web_search_require_allowed_domain and not self.web_search_allowed_domains:
            raise ValueError("web_search_require_allowed_domain requires at least one allowed domain.")
        return self

    @property
    def agent_name(self) -> str:
        return _scoped_agent_name("analyst", self.name)

    @property
    def routing_terms(self) -> list[str]:
        return [
            *self.routing_keywords,
            *_routing_terms([
                self.name,
                self.description or "",
                *self.enabled_modes,
                *self.semantic_model_ids,
                *self.dataset_ids,
                *(self.web_search_focus_terms if self.web_search_enabled else []),
                *(self.web_search_allowed_domains if self.web_search_enabled else []),
            ]),
        ]

    @property
    def supports_research(self) -> bool:
        return self.deep_research_enabled or any(
            mode in {"research", "deep_research", "hybrid"} for mode in self.enabled_modes
        )


class WebSearchToolScope(BaseModel):
    name: str = "web-search"
    description: str | None = None
    provider: str | None = None
    allowed_domains: list[str] = Field(default_factory=list)
    denied_domains: list[str] = Field(default_factory=list)
    require_allowed_domain: bool = False
    provider_required: bool = False
    focus_terms: list[str] = Field(default_factory=list)
    max_results: int = 6
    region: str | None = None
    safe_search: str | None = None
    timebox_seconds: int = 10
    routing_keywords: list[str] = Field(default_factory=list)
    routing_phrases: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_domain_policy(self) -> "WebSearchToolScope":
        if self.require_allowed_domain and not self.allowed_domains:
            raise ValueError("require_allowed_domain requires at least one allowed domain.")
        return self

    @property
    def routing_terms(self) -> list[str]:
        return [
            *self.routing_keywords,
            *_routing_terms([
                self.name,
                self.description or "",
                *self.allowed_domains,
                *self.focus_terms,
            ]),
        ]


class AgentProfile(BaseModel):
    name: str
    description: str | None = None
    default: bool = False
    instructions: str | None = None
    features: AgentProfileFeatures = Field(default_factory=AgentProfileFeatures)
    execution: AgentProfileExecution = Field(default_factory=AgentProfileExecution)
    access_policy: AgentProfileAccessPolicy = Field(default_factory=AgentProfileAccessPolicy)
    analyst_scopes: list[AnalystAgentScope] = Field(default_factory=list)
    web_search_scopes: list[WebSearchToolScope] = Field(default_factory=list)

    @classmethod
    def from_config(cls, config: Mapping[str, Any] | Any) -> "AgentProfile":
        name = str(_config_value(config, "name") or "").strip()
        if not name:
            raise ValueError("Agent profile config requires a name.")
        definition = _config_value(config, "definition")
        if isinstance(definition, Mapping) and definition:
            return cls.from_definition(
                name=name,
                description=_config_value(config, "description"),
                default=bool(_config_value(config, "default", False)),
                definition=definition,
            )

        semantic_model = str(_config_value(config, "semantic_model") or "").strip()
        dataset = str(_config_value(config, "dataset") or "").strip()
        if not semantic_model and not dataset:
            raise ValueError(
                "Agent profile config requires definition, semantic_model, or dataset."
            )
        scope = AnalystAgentScope(
            name=f"{name}_sql",
            description=_config_value(config, "description"),
            semantic_model_ids=[semantic_model] if semantic_model else [],
            dataset_ids=[dataset] if dataset else [],
        )
        return cls(
            name=name,
            description=_config_value(config, "description"),
            default=bool(_config_value(config, "default", False)),
            instructions=_config_value(config, "instructions"),
            analyst_scopes=[scope],
        )

    @classmethod
    def from_definition(
        cls,
        *,
        name: str,
        description: str | None = None,
        default: bool = False,
        definition: Mapping[str, Any],
    ) -> "AgentProfile":
        payload = dict(definition)
        features = AgentProfileFeatures.model_validate(payload.get("features") or {})
        execution = AgentProfileExecution.model_validate(payload.get("execution") or {})
        access_policy = AgentProfileAccessPolicy.model_validate(payload.get("access_policy") or {})

        analyst_scopes: list[AnalystAgentScope] = []
        web_search_scopes: list[WebSearchToolScope] = []
        for tool in payload.get("tools") or []:
            if not isinstance(tool, Mapping):
                continue
            tool_type = str(tool.get("tool_type") or "").strip().casefold()
            config = tool.get("config") if isinstance(tool.get("config"), Mapping) else {}
            tool_name = str(tool.get("name") or "").strip()
            tool_description = str(tool.get("description") or "").strip() or None
            if tool_type == "sql":
                tool_deep_research_enabled = bool(
                    config.get("deep_research_enabled", features.deep_research_enabled)
                )
                enabled_modes = ["quick", "semantic", "sql"]
                if tool_deep_research_enabled:
                    enabled_modes.extend(["research", "deep_research", "hybrid"])
                analyst_scopes.append(
                    AnalystAgentScope(
                        name=tool_name or f"{name}_sql",
                        description=tool_description,
                        enabled_modes=enabled_modes,
                        deep_research_enabled=tool_deep_research_enabled,
                        semantic_model_ids=_string_list(config.get("semantic_model_ids")),
                        dataset_ids=_string_list(config.get("dataset_ids")),
                        query_scope_policy=str(
                            config.get("query_scope_policy") or "semantic_preferred"
                        ),
                        allow_source_scope=bool(config.get("allow_source_scope")),
                        preferred_dataset_id=(
                            str(config.get("preferred_dataset_id"))
                            if config.get("preferred_dataset_id") is not None
                            else None
                        ),
                        preferred_semantic_model_id=(
                            str(config.get("preferred_semantic_model_id"))
                            if config.get("preferred_semantic_model_id") is not None
                            else None
                        ),
                        allowed_connectors=list(access_policy.allowed_connectors),
                        denied_connectors=list(access_policy.denied_connectors),
                    )
                )
            elif tool_type in {"web", "web_search"}:
                web_scope = WebSearchToolScope(
                    name=tool_name or f"{name}_web_search",
                    description=tool_description,
                    provider=(
                        str(config.get("provider")) if config.get("provider") is not None else None
                    ),
                    allowed_domains=_string_list(config.get("allowed_domains")),
                    denied_domains=_string_list(config.get("denied_domains")),
                    require_allowed_domain=bool(config.get("require_allowed_domain")),
                    provider_required=bool(config.get("provider_required", True)),
                    focus_terms=_string_list(config.get("focus_terms")),
                    max_results=int(config.get("max_results") or 6),
                    region=(
                        str(config.get("region")) if config.get("region") is not None else None
                    ),
                    safe_search=(
                        str(config.get("safe_search"))
                        if config.get("safe_search") is not None
                        else None
                    ),
                    timebox_seconds=int(config.get("timebox_seconds") or 10),
                )
                web_search_scopes.append(web_scope)

        if web_search_scopes and not analyst_scopes:
            analyst_scopes.append(
                AnalystAgentScope(
                    name=f"{name}_analyst",
                    description=description,
                    deep_research_enabled=features.deep_research_enabled,
                )
            )

        if features.deep_research_enabled or web_search_scopes:
            for scope in analyst_scopes:
                scope.deep_research_enabled = scope.deep_research_enabled or features.deep_research_enabled
                scope.enabled_modes = list(
                    dict.fromkeys([*scope.enabled_modes, "research", "deep_research", "hybrid"])
                )
                scope.require_sources = bool(web_search_scopes)
                for web_scope in web_search_scopes:
                    scope.web_search_enabled = True
                    scope.web_search_name = web_scope.name
                    scope.web_search_provider = web_scope.provider
                    scope.web_search_allowed_domains = list(
                        dict.fromkeys([*scope.web_search_allowed_domains, *web_scope.allowed_domains])
                    )
                    scope.web_search_denied_domains = list(
                        dict.fromkeys([*scope.web_search_denied_domains, *web_scope.denied_domains])
                    )
                    scope.web_search_require_allowed_domain = (
                        scope.web_search_require_allowed_domain or web_scope.require_allowed_domain
                    )
                    scope.web_search_provider_required = (
                        scope.web_search_provider_required or web_scope.provider_required
                    )
                    scope.web_search_focus_terms = list(
                        dict.fromkeys([*scope.web_search_focus_terms, *web_scope.focus_terms])
                    )
                    scope.web_search_max_results = web_scope.max_results
                    scope.web_search_region = web_scope.region
                    scope.web_search_safe_search = web_scope.safe_search
                    scope.web_search_timebox_seconds = web_scope.timebox_seconds
                    scope.routing_keywords = list(dict.fromkeys([*scope.routing_keywords, *web_scope.routing_terms]))

        prompt = payload.get("prompt") if isinstance(payload.get("prompt"), Mapping) else {}
        instructions = str(prompt.get("user_instructions") or "").strip() or None
        return cls(
            name=name,
            description=description,
            default=default,
            instructions=instructions,
            features=features,
            execution=execution,
            access_policy=access_policy,
            analyst_scopes=analyst_scopes,
            web_search_scopes=web_search_scopes,
        )


@dataclass(frozen=True)
class AgentProfileRuntime:
    profile: AgentProfile
    registry: AgentRegistry
    meta_controller: Any


class AgentProfileRegistryBuilder:
    """Builds one scoped specialist registry for one configured agent profile."""

    def build_registry(
        self,
        profile: AgentProfile,
        *,
        llm_provider: Any,
        sql_analysis_tools: Mapping[str, list[Any]] | None = None,
        semantic_search_tools: Mapping[str, list[Any]] | None = None,
        web_search_providers: Mapping[str, Any] | None = None,
    ) -> AgentRegistry:
        from langbridge.ai.agents.analyst import AnalystAgent
        from langbridge.ai.tools.web_search import WebSearchPolicy, WebSearchTool, create_web_search_provider

        sql_tools = dict(sql_analysis_tools or {})
        semantic_tools = dict(semantic_search_tools or {})
        providers = dict(web_search_providers or {})
        agents = []
        for scope in profile.analyst_scopes:
            provider = (
                providers.get(scope.web_search_name or "")
                or providers.get(scope.web_search_provider or "")
                or providers.get(scope.name)
                or providers.get(scope.agent_name)
            )
            web_tool = None
            if scope.web_search_enabled:
                provider = provider or create_web_search_provider(scope.web_search_provider)
                web_tool = WebSearchTool(
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
            agents.append(
                AnalystAgent(
                    llm_provider=llm_provider,
                    scope=scope,
                    sql_analysis_tools=sql_tools.get(scope.name) or sql_tools.get(scope.agent_name) or [],
                    semantic_search_tools=semantic_tools.get(scope.name) or semantic_tools.get(scope.agent_name) or [],
                    web_search_tool=web_tool,
                )
            )
        return AgentRegistry(agents)

    def build_runtime(
        self,
        profile: AgentProfile,
        *,
        llm_provider: Any,
        sql_analysis_tools: Mapping[str, list[Any]] | None = None,
        semantic_search_tools: Mapping[str, list[Any]] | None = None,
        web_search_providers: Mapping[str, Any] | None = None,
    ) -> AgentProfileRuntime:
        from langbridge.ai.agents.presentation import PresentationAgent
        from langbridge.ai.tools.charting import ChartingTool
        from langbridge.ai.meta_controller import MetaControllerAgent

        registry = self.build_registry(
            profile,
            llm_provider=llm_provider,
            sql_analysis_tools=sql_analysis_tools,
            semantic_search_tools=semantic_search_tools,
            web_search_providers=web_search_providers,
        )
        controller = MetaControllerAgent(
            registry=registry,
            presentation_agent=PresentationAgent(
                llm_provider=llm_provider,
                charting_tool=ChartingTool(llm_provider=llm_provider),
            ),
            max_iterations=profile.execution.max_iterations,
            max_step_retries=1,
        )
        return AgentProfileRuntime(
            profile=profile,
            registry=registry,
            meta_controller=controller,
        )


__all__ = [
    "AgentProfile",
    "AgentProfileAccessPolicy",
    "AgentProfileExecution",
    "AgentProfileFeatures",
    "AgentProfileRegistryBuilder",
    "AgentProfileRuntime",
    "AnalystAgentScope",
    "WebSearchToolScope",
]
