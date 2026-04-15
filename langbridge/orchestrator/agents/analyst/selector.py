"""
Scope-aware analytical binding selection for layered analyst execution.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Sequence

from langbridge.orchestrator.definitions import AnalystQueryScopePolicy
from langbridge.orchestrator.llm.provider import LLMProvider
from langbridge.orchestrator.tools.sql_analyst.interfaces import AnalystQueryRequest
from langbridge.orchestrator.tools.sql_analyst.tool import SqlAnalystTool
from langbridge.runtime.models import SqlQueryScope

TOKEN_RE = re.compile(r"\b\w+\b")
SOURCE_HINT_RE = re.compile(
    r"\b(source|raw|connector|underlying|physical|debug|direct sql|direct query)\b",
    re.IGNORECASE,
)


class ToolSelectionError(RuntimeError):
    """Raised when the agent cannot determine an appropriate analytical context."""


@dataclass(frozen=True)
class ToolCandidate:
    tool: SqlAnalystTool
    score: float
    priority: int
    order: int


@dataclass(frozen=True)
class BindingCandidate:
    binding_name: str
    score: float
    priority: int
    order: int


@dataclass
class _BindingGroup:
    name: str
    description: str | None
    query_scope_policy: AnalystQueryScopePolicy
    tools_by_scope: dict[SqlQueryScope, list[SqlAnalystTool]] = field(default_factory=dict)
    keywords: set[str] = field(default_factory=set)
    priority: int = 0
    order: int = 0

    @property
    def available_scopes(self) -> tuple[SqlQueryScope, ...]:
        scopes = [scope for scope, tools in self.tools_by_scope.items() if tools]
        return tuple(scopes)


@dataclass(frozen=True)
class AnalyticalBindingSelection:
    binding_name: str
    query_scope_policy: AnalystQueryScopePolicy
    initial_scope: SqlQueryScope
    available_scopes: tuple[SqlQueryScope, ...]


class AnalyticalContextSelector:
    """
    Select the analytical binding first, then the best scope and asset within it.
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: Sequence[SqlAnalystTool],
    ) -> None:
        if not tools:
            raise ValueError("AnalyticalContextSelector requires at least one analytical tool.")

        self._llm = llm
        self._tools = list(tools)
        self._bindings = self._build_bindings(self._tools)

    def select_binding(self, request: AnalystQueryRequest) -> AnalyticalBindingSelection:
        if not self._bindings:
            raise ToolSelectionError("No analytical tools are available for selection.")

        binding = self._select_binding_group(request)
        initial_scope = self._select_initial_scope(binding=binding, request=request)
        return AnalyticalBindingSelection(
            binding_name=binding.name,
            query_scope_policy=binding.query_scope_policy,
            initial_scope=initial_scope,
            available_scopes=binding.available_scopes,
        )

    def select_tool(
        self,
        request: AnalystQueryRequest,
        *,
        binding_name: str,
        query_scope: SqlQueryScope,
    ) -> SqlAnalystTool:
        binding = self._bindings.get(binding_name)
        if binding is None:
            raise ToolSelectionError(f"Analytical binding '{binding_name}' is not available.")

        scoped_tools = list(binding.tools_by_scope.get(query_scope, []))
        if not scoped_tools:
            raise ToolSelectionError(
                f"Analytical binding '{binding_name}' does not expose query scope '{query_scope.value}'."
            )
        if len(scoped_tools) == 1:
            return scoped_tools[0]

        try:
            llm_choice = self._select_tool_with_llm(
                request=request,
                binding=binding,
                query_scope=query_scope,
                scoped_tools=scoped_tools,
            )
            if llm_choice is not None:
                return llm_choice
        except Exception:
            pass

        return self._fallback_select_tool(request=request, scoped_tools=scoped_tools)

    def fallback_scope(
        self,
        selection: AnalyticalBindingSelection,
        *,
        current_scope: SqlQueryScope,
    ) -> SqlQueryScope | None:
        binding = self._bindings.get(selection.binding_name)
        if binding is None:
            return None
        available = set(binding.available_scopes)
        if (
            selection.query_scope_policy == AnalystQueryScopePolicy.semantic_preferred
            and current_scope == SqlQueryScope.semantic
            and SqlQueryScope.dataset in available
        ):
            return SqlQueryScope.dataset
        if (
            selection.query_scope_policy == AnalystQueryScopePolicy.dataset_preferred
            and current_scope == SqlQueryScope.dataset
            and SqlQueryScope.semantic in available
        ):
            return SqlQueryScope.semantic
        return None

    @staticmethod
    def _build_bindings(tools: Sequence[SqlAnalystTool]) -> dict[str, _BindingGroup]:
        bindings: dict[str, _BindingGroup] = {}
        for order, tool in enumerate(tools):
            binding = bindings.get(tool.binding_name)
            if binding is None:
                binding = _BindingGroup(
                    name=tool.binding_name,
                    description=tool.binding_description,
                    query_scope_policy=tool.query_scope_policy,
                    order=order,
                )
                bindings[tool.binding_name] = binding
            elif binding.query_scope_policy != tool.query_scope_policy:
                raise ValueError(
                    f"Analytical binding '{tool.binding_name}' mixes incompatible query scope policies."
                )
            if not binding.description and tool.binding_description:
                binding.description = tool.binding_description
            binding.tools_by_scope.setdefault(tool.query_scope, []).append(tool)
            binding.keywords.update(tool.selection_keywords())
            binding.priority = max(binding.priority, int(getattr(tool, "priority", 0)))
        return bindings

    def _select_binding_group(self, request: AnalystQueryRequest) -> _BindingGroup:
        bindings = list(self._bindings.values())
        if len(bindings) == 1:
            return bindings[0]

        try:
            llm_choice = self._select_binding_with_llm(request, bindings)
            if llm_choice is not None:
                return llm_choice
        except Exception:
            pass

        return self._fallback_select_binding(request, bindings)

    def _select_binding_with_llm(
        self,
        request: AnalystQueryRequest,
        bindings: Sequence[_BindingGroup],
    ) -> _BindingGroup | None:
        prompt = self._build_binding_prompt(request, bindings)
        response_text = self._llm.complete(prompt=prompt, temperature=0.0)

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            return None

        binding_id = str(data.get("binding_id") or data.get("binding") or "").strip()
        if not binding_id:
            return None
        return self._bindings.get(binding_id)

    def _build_binding_prompt(
        self,
        request: AnalystQueryRequest,
        bindings: Sequence[_BindingGroup],
    ) -> str:
        payload = []
        for binding in bindings:
            payload.append(
                {
                    "id": binding.name,
                    "description": binding.description,
                    "query_scope_policy": binding.query_scope_policy.value,
                    "available_scopes": [scope.value for scope in binding.available_scopes],
                    "assets": [
                        {
                            "scope": scope.value,
                            "asset_name": tool.context.asset_name,
                            "asset_type": tool.context.asset_type,
                            "metrics": [metric.name for metric in tool.context.metrics],
                            "dimensions": [field.name for field in tool.context.dimensions[:8]],
                            "datasets": [dataset.dataset_name for dataset in tool.context.datasets],
                            "tags": list(tool.context.tags or []),
                        }
                        for scope, tools in binding.tools_by_scope.items()
                        for tool in tools
                    ],
                    "keywords": sorted(binding.keywords),
                }
            )

        return f"""
You are routing an analytics request to the best analytical binding.

Each binding represents one analytical domain. Choose the binding whose governed metrics,
dimensions, datasets, and tags best match the request. Do not choose a binding just because
it exposes dataset scope or lower-level access.

Return STRICT JSON and nothing else:
{{
  "binding_id": "<ID of the chosen binding>",
  "reason": "<very short explanation>"
}}

Question:
{request.question.strip()}

Filters (if any):
{json.dumps(request.filters or {}, indent=2)}

Available analytical bindings:
{json.dumps(payload, indent=2, default=str)}
""".strip()

    def _fallback_select_binding(
        self,
        request: AnalystQueryRequest,
        bindings: Sequence[_BindingGroup],
    ) -> _BindingGroup:
        tokens = self._request_tokens(request)
        candidates: list[BindingCandidate] = []
        for binding in bindings:
            score = self._score(tokens, binding.keywords)
            candidates.append(
                BindingCandidate(
                    binding_name=binding.name,
                    score=score,
                    priority=binding.priority,
                    order=binding.order,
                )
            )

        best = max(
            candidates,
            key=lambda candidate: (candidate.score, candidate.priority, -candidate.order),
        )
        return self._bindings[best.binding_name]

    def _select_initial_scope(
        self,
        *,
        binding: _BindingGroup,
        request: AnalystQueryRequest,
    ) -> SqlQueryScope:
        available = set(binding.available_scopes)
        if not available:
            raise ToolSelectionError(f"Analytical binding '{binding.name}' has no available analytical scopes.")

        if binding.query_scope_policy == AnalystQueryScopePolicy.semantic_only:
            if SqlQueryScope.semantic not in available:
                raise ToolSelectionError(
                    f"Analytical binding '{binding.name}' requires semantic scope, but no semantic asset is available."
                )
            return SqlQueryScope.semantic

        if binding.query_scope_policy == AnalystQueryScopePolicy.dataset_only:
            if SqlQueryScope.dataset not in available:
                raise ToolSelectionError(
                    f"Analytical binding '{binding.name}' requires dataset scope, but no dataset asset is available."
                )
            return SqlQueryScope.dataset

        if binding.query_scope_policy == AnalystQueryScopePolicy.semantic_preferred:
            if SqlQueryScope.semantic in available:
                return SqlQueryScope.semantic
            if SqlQueryScope.dataset in available:
                return SqlQueryScope.dataset

        if binding.query_scope_policy == AnalystQueryScopePolicy.dataset_preferred:
            if SqlQueryScope.dataset in available:
                return SqlQueryScope.dataset
            if SqlQueryScope.semantic in available:
                return SqlQueryScope.semantic

        if SqlQueryScope.source in available and self._source_requested(request):
            return SqlQueryScope.source

        raise ToolSelectionError(
            f"Analytical binding '{binding.name}' has no valid scope for policy '{binding.query_scope_policy.value}'."
        )

    def _select_tool_with_llm(
        self,
        *,
        request: AnalystQueryRequest,
        binding: _BindingGroup,
        query_scope: SqlQueryScope,
        scoped_tools: Sequence[SqlAnalystTool],
    ) -> SqlAnalystTool | None:
        descriptions = {
            str(idx): tool.describe_for_selection(tool_id=str(idx))
            for idx, tool in enumerate(scoped_tools)
        }
        prompt = f"""
You are routing an analytics request inside one analytical binding.

The binding has already been chosen. Now choose the single best analytical asset
within query scope '{query_scope.value}'.

Return STRICT JSON and nothing else:
{{
  "tool_id": "<ID of the chosen asset>",
  "reason": "<very short explanation>"
}}

Binding:
{binding.name}

Question:
{request.question.strip()}

Filters (if any):
{json.dumps(request.filters or {}, indent=2)}

Scoped analytical assets:
{json.dumps(list(descriptions.values()), indent=2, default=str)}
""".strip()
        response_text = self._llm.complete(prompt=prompt, temperature=0.0)
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        tool_id = str(data.get("tool_id") or data.get("tool") or "").strip()
        if not tool_id:
            return None
        if tool_id not in descriptions:
            return None
        try:
            return scoped_tools[int(tool_id)]
        except (TypeError, ValueError, IndexError):
            return None

    def _fallback_select_tool(
        self,
        *,
        request: AnalystQueryRequest,
        scoped_tools: Sequence[SqlAnalystTool],
    ) -> SqlAnalystTool:
        tokens = self._request_tokens(request)
        candidates: list[ToolCandidate] = []
        for idx, tool in enumerate(scoped_tools):
            score = self._score(tokens, tool.selection_keywords())
            candidates.append(
                ToolCandidate(
                    tool=tool,
                    score=score,
                    priority=getattr(tool, "priority", 0),
                    order=idx,
                )
            )

        best = max(
            candidates,
            key=lambda candidate: (candidate.score, candidate.priority, -candidate.order),
        )
        return best.tool

    @staticmethod
    def _request_tokens(request: AnalystQueryRequest) -> set[str]:
        tokens = AnalyticalContextSelector._tokenize(request.question)
        if request.filters:
            tokens.update(AnalyticalContextSelector._tokenize(" ".join(request.filters.keys())))
        return tokens

    @staticmethod
    def _source_requested(request: AnalystQueryRequest) -> bool:
        question = str(request.question or "")
        context = str(request.conversation_context or "")
        return bool(SOURCE_HINT_RE.search(question) or SOURCE_HINT_RE.search(context))

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token.lower() for token in TOKEN_RE.findall(text or "")}

    @staticmethod
    def _score(tokens: set[str], keywords: set[str]) -> float:
        if not keywords:
            return 0.0
        matches = tokens.intersection(keywords)
        return float(len(matches)) / float(len(keywords))


__all__ = [
    "AnalyticalBindingSelection",
    "AnalyticalContextSelector",
    "ToolSelectionError",
]
