"""Specification-driven analyst agent for Langbridge AI."""

import json
from dataclasses import dataclass
from typing import Any, Sequence

from langbridge.ai.base import (
    AgentCostLevel,
    AgentIOContract,
    AgentResult,
    AgentResultStatus,
    AgentRoutingSpec,
    AgentSpecification,
    AgentTask,
    AgentTaskKind,
    AgentToolSpecification,
    BaseAgent,
)
from langbridge.ai.events import AIEventEmitter, AIEventSource
from langbridge.ai.agents.analyst.prompts import (
    ANALYST_CONTEXT_ANALYSIS_PROMPT,
    ANALYST_DEEP_RESEARCH_PROMPT,
    ANALYST_MODE_SELECTION_PROMPT,
    ANALYST_SQL_RESPONSE_PROMPT,
    ANALYST_SQL_TOOL_SELECTION_PROMPT,
)
from langbridge.ai.llm.base import LLMProvider
from langbridge.ai.modes import AnalystAgentMode, normalize_analyst_mode
from langbridge.ai.profiles import AnalystAgentConfig
from langbridge.ai.tools.semantic_search import SemanticSearchTool
from langbridge.ai.tools.sql import SqlAnalysisTool
from langbridge.ai.tools.sql.interfaces import (
    AnalystOutcomeStatus,
    AnalystQueryRequest,
    AnalystQueryResponse,
    AnalystRecoveryAction,
    SqlQueryScope,
)
from langbridge.ai.tools.web_search import WebSearchResult, WebSearchTool


_SEMANTIC_FALLBACK_MARKERS = (
    "semantic sql scope does not support",
    "semantic scope does not support",
    "semantic query translation failed",
    "unknown semantic member",
    "could not resolve a selected semantic member",
    "semantic model not found",
    "semantic coverage gap",
    "unsupported semantic sql shape",
)


@dataclass(frozen=True, slots=True)
class SqlFailureTaxonomy:
    kind: str
    status: str | None
    stage: str | None
    message: str | None
    fallback_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
            "fallback_eligible": self.fallback_eligible,
        }


class AnalystAgent(AIEventSource, BaseAgent):
    """Performs governed analytical work and research for one analyst profile."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        config: AnalystAgentConfig,
        sql_analysis_tools: Sequence[SqlAnalysisTool] | None = None,
        semantic_search_tools: Sequence[SemanticSearchTool] | None = None,
        web_search_tool: WebSearchTool | None = None,
        event_emitter: AIEventEmitter | None = None,
    ) -> None:
        super().__init__(event_emitter=event_emitter)
        self._llm = llm_provider
        self._config = config
        self._sql_tools = list(sql_analysis_tools or [])
        self._semantic_search_tools = list(semantic_search_tools or [])
        self._web_search_tool = web_search_tool

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name=self._config.agent_name,
            description=self._config.description
            or "Answers governed analytical questions and source-backed research requests.",
            task_kinds=[AgentTaskKind.analyst],
            capabilities=self._capabilities(),
            constraints=self._constraints(),
            routing=AgentRoutingSpec(
                keywords=["analyze", "metric", "trend", "research", "compare", "summarize"],
                phrases=["what is", "what are", "show", "compare", "break down"],
                direct_threshold=2,
                planner_threshold=4,
            ),
            input_contract=AgentIOContract(optional_keys=["agent_mode", "force_web_search"]),
            output_contract=AgentIOContract(
                required_keys=["analysis", "result"],
                optional_keys=[
                    "analysis_path",
                    "sql_canonical",
                    "sql_executable",
                    "selected_datasets",
                    "selected_semantic_models",
                    "query_scope",
                    "outcome",
                    "error_taxonomy",
                    "synthesis",
                    "findings",
                    "sources",
                    "follow_ups",
                ],
            ),
            tools=self._tool_specifications(),
            metadata={
                "scope": {
                    "semantic_models": self._config.semantic_model_ids,
                    "datasets": self._config.dataset_ids,
                    "query_policy": self._config.query_policy,
                    "allow_source_scope": self._config.allow_source_scope,
                    "research_enabled": self._config.supports_research,
                    "extended_thinking_enabled": self._config.supports_extended_thinking,
                    "web_search_enabled": self._config.web_search_enabled,
                    "web_search_allowed_domains": self._config.web_search_allowed_domains,
                    "allowed_connectors": list(self._config.access.allowed_connectors),
                    "denied_connectors": list(self._config.access.denied_connectors),
                },
                "supported_modes": [mode.value for mode in self._supported_modes()],
            },
        )

    async def execute(self, task: AgentTask) -> AgentResult:
        if task.task_kind != AgentTaskKind.analyst:
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                error=f"Analyst agent only supports '{AgentTaskKind.analyst.value}' tasks.",
            )
        if not task.question.strip():
            return self.build_result(
                task=task,
                status=AgentResultStatus.needs_clarification,
                error="Question is required for analyst work.",
            )

        try:
            requested_mode = self._requested_mode(task)
        except ValueError as exc:
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                error=str(exc),
            )
        if requested_mode == AnalystAgentMode.auto:
            await self._emit_ai_event(
                event_type="AnalystModeSelectionStarted",
                message="Choosing analyst execution mode.",
                source=self.specification.name,
            )
            decision = await self._select_execution_mode(task)
            selected_mode = str(decision.get("agent_mode") or "").strip().lower()
            if selected_mode == "clarify":
                return self.build_result(
                    task=task,
                    status=AgentResultStatus.needs_clarification,
                    error=str(
                        decision.get("clarification_question") or decision.get("reason") or "Clarification needed."
                    ),
                    diagnostics={"mode_decision": decision},
                )
            normalized_mode = normalize_analyst_mode(selected_mode, default=AnalystAgentMode.sql)
            if normalized_mode is None:
                raise ValueError("Analyst mode selection returned no mode.")
            mode = normalized_mode
            await self._emit_ai_event(
                event_type="AnalystModeSelected",
                message=f"Selected {mode.value} mode.",
                source=self.specification.name,
                details={"agent_mode": mode.value, "reason": decision.get("reason")},
            )
        else:
            decision = {"agent_mode": requested_mode.value, "reason": "Mode forced by task input."}
            mode = requested_mode

        if mode == AnalystAgentMode.research:
            return await self._execute_research(task, mode_decision=decision)
        if mode == AnalystAgentMode.sql:
            return await self._execute_sql(task, mode_decision=decision)
        if mode == AnalystAgentMode.context_analysis:
            return await self._execute_llm_analysis(task, mode_decision=decision)

        raise ValueError(f"Unsupported analyst execution mode: {mode.value}")

    async def _execute_sql(self, task: AgentTask, *, mode_decision: dict[str, Any]) -> AgentResult:
        candidate_tools = self._initial_sql_tools()
        if not candidate_tools:
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                error="No SQL analysis tools are configured for this analyst profile.",
                diagnostics={"agent_mode": AnalystAgentMode.sql.value, "mode_decision": mode_decision},
            )

        await self._emit_ai_event(
            event_type="AgentToolStarted",
            message="Selecting SQL analysis tool.",
            source=self.specification.name,
        )
        selected_tool = await self._select_sql_tool(
            question=task.question,
            tools=candidate_tools,
            memory_context=self._memory_context(task.context),
        )
        await self._emit_ai_event(
            event_type="AgentToolSelected",
            message=f"Selected SQL tool {selected_tool.name}.",
            source=self.specification.name,
            details={
                "tool": selected_tool.name,
                "asset_type": selected_tool.asset_type,
                "query_scope": selected_tool.query_scope.value,
            },
        )

        request = self._sql_request(task)
        response = await selected_tool.arun(request)
        taxonomy = self._classify_sql_failure(response=response, tool=selected_tool)
        final_tool = selected_tool
        fallback_details: dict[str, Any] | None = None

        if taxonomy.fallback_eligible:
            fallback_tool = await self._select_fallback_tool(
                question=task.question,
                current_tool=selected_tool,
                memory_context=self._memory_context(task.context),
            )
            if fallback_tool is not None:
                await self._emit_ai_event(
                    event_type="AnalystScopeFallbackStarted",
                    message=(
                        f"Falling back from {selected_tool.query_scope.value} scope to "
                        f"{fallback_tool.query_scope.value} scope."
                    ),
                    source=self.specification.name,
                    details={
                        "from_tool": selected_tool.name,
                        "to_tool": fallback_tool.name,
                        "reason": taxonomy.message,
                        "error_kind": taxonomy.kind,
                    },
                )
                fallback_request = request.model_copy(
                    update={
                        "error_history": [*request.error_history, taxonomy.message or response.error or ""],
                        "error_retries": 0,
                    }
                )
                fallback_response = await fallback_tool.arun(fallback_request)
                response = self._apply_scope_fallback(
                    fallback_response=fallback_response,
                    original_response=response,
                    from_tool=selected_tool,
                    to_tool=fallback_tool,
                    taxonomy=taxonomy,
                )
                final_tool = fallback_tool
                fallback_details = {
                    "from_tool": selected_tool.name,
                    "to_tool": fallback_tool.name,
                    "from_scope": selected_tool.query_scope.value,
                    "to_scope": fallback_tool.query_scope.value,
                    "reason": taxonomy.message,
                    "error_kind": taxonomy.kind,
                }
                await self._emit_ai_event(
                    event_type="AnalystScopeFallbackCompleted",
                    message=f"Retrying with dataset-native scope via {fallback_tool.name}.",
                    source=self.specification.name,
                    details=fallback_details,
                )

        await self._emit_ai_event(
            event_type="AnalystSummaryStarted",
            message="Summarizing SQL analysis result.",
            source=self.specification.name,
            details={"tool": final_tool.name},
        )
        summary = await self._summarize_sql_response(
            question=task.question,
            response=response,
            memory_context=self._memory_context(task.context),
        )
        output = self._build_sql_output(summary=summary, response=response, taxonomy=taxonomy)
        status = self._result_status_for_sql(response)
        diagnostics = {
            "agent_mode": AnalystAgentMode.sql.value,
            "mode_decision": mode_decision,
            "selected_tool": final_tool.name,
            "selected_query_scope": final_tool.query_scope.value,
            "error_taxonomy": taxonomy.to_dict(),
        }
        if fallback_details is not None:
            diagnostics["fallback"] = fallback_details
        return self.build_result(
            task=task,
            status=status,
            output=output,
            diagnostics=diagnostics,
            error=response.error if status != AgentResultStatus.succeeded else None,
        )

    async def _execute_research(
        self,
        task: AgentTask,
        *,
        mode_decision: dict[str, Any],
    ) -> AgentResult:
        await self._emit_ai_event(
            event_type="DeepResearchStarted",
            message="Gathering evidence for research answer.",
            source=self.specification.name,
        )
        if not self._config.supports_research:
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                error="Research mode is not enabled for this analyst profile.",
                diagnostics={"agent_mode": AnalystAgentMode.research.value, "mode_decision": mode_decision},
            )
        sources = self._collect_sources(task.context)
        web_result = await self._run_web_search_if_needed(task=task, existing_sources=sources)
        if web_result is not None:
            sources.extend([item.to_dict() for item in web_result.results])
        sources = sources[: self._config.max_sources]
        if self._config.require_sources and not sources:
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                output={"analysis": "", "result": {}, "synthesis": "", "findings": [], "sources": []},
                error="Research mode requires sources, but no evidence was available.",
                diagnostics={"agent_mode": AnalystAgentMode.research.value, "mode_decision": mode_decision},
            )
        research = await self._synthesize_research(
            question=task.question,
            sources=sources,
            memory_context=self._memory_context(task.context),
        )
        await self._emit_ai_event(
            event_type="DeepResearchCompleted",
            message=f"Synthesized research from {len(sources)} source(s).",
            source=self.specification.name,
            details={"source_count": len(sources)},
        )
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={
                "analysis": research["synthesis"],
                "result": {},
                "synthesis": research["synthesis"],
                "findings": research.get("findings", []),
                "sources": sources,
                "follow_ups": research.get("follow_ups", []),
                "selected_datasets": self._config.dataset_ids,
                "selected_semantic_models": self._config.semantic_model_ids,
                "query_scope": self._config.query_policy,
            },
            diagnostics={
                "agent_mode": AnalystAgentMode.research.value,
                "mode_decision": mode_decision,
                "web_search": web_result.to_dict() if web_result else None,
            },
        )

    async def _execute_llm_analysis(
        self,
        task: AgentTask,
        *,
        mode_decision: dict[str, Any],
    ) -> AgentResult:
        await self._emit_ai_event(
            event_type="AnalystContextAnalysisStarted",
            message="Analyzing provided result context.",
            source=self.specification.name,
        )
        context_result = task.context.get("result")
        if not isinstance(context_result, dict):
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                error="No structured result context is available for context analysis mode.",
                diagnostics={"agent_mode": AnalystAgentMode.context_analysis.value, "mode_decision": mode_decision},
            )
        prompt = self._prompt(
            ANALYST_CONTEXT_ANALYSIS_PROMPT.format(
                question=task.question,
                memory_context=self._memory_context(task.context),
                result=json.dumps(context_result, default=str),
            )
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=800))
        result = parsed.get("result")
        if not isinstance(result, dict):
            raise ValueError("Analyst LLM response missing object field: result.")
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"analysis": str(parsed.get("analysis") or ""), "result": result},
            diagnostics={"agent_mode": AnalystAgentMode.context_analysis.value, "mode_decision": mode_decision},
        )

    async def _select_sql_tool(
        self,
        *,
        question: str,
        tools: Sequence[SqlAnalysisTool],
        memory_context: str = "",
    ) -> SqlAnalysisTool:
        if len(tools) == 1:
            return tools[0]
        prompt = self._prompt(
            ANALYST_SQL_TOOL_SELECTION_PROMPT.format(
                question=question,
                memory_context=memory_context,
                filters="{}",
                tools=json.dumps([tool.describe() for tool in tools], default=str, indent=2),
            )
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=400))
        selected_name = str(parsed.get("tool_name") or "").strip()
        for tool in tools:
            if tool.name == selected_name:
                return tool
        raise ValueError(f"LLM selected unknown SQL analysis tool: {selected_name}")

    async def _select_fallback_tool(
        self,
        *,
        question: str,
        current_tool: SqlAnalysisTool,
        memory_context: str = "",
    ) -> SqlAnalysisTool | None:
        tools = self._fallback_sql_tools(current_tool)
        if not tools:
            return None
        return await self._select_sql_tool(question=question, tools=tools, memory_context=memory_context)

    async def _summarize_sql_response(
        self,
        *,
        question: str,
        response: AnalystQueryResponse,
        memory_context: str = "",
    ) -> str:
        prompt = self._prompt(
            ANALYST_SQL_RESPONSE_PROMPT.format(
                question=question,
                memory_context=memory_context,
                sql=response.sql_canonical,
                result=json.dumps(response.result.model_dump(mode="json") if response.result else {}, default=str),
                outcome=json.dumps(response.outcome.model_dump(mode="json") if response.outcome else {}, default=str),
            )
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=700))
        analysis = str(parsed.get("analysis") or "").strip()
        if not analysis:
            raise ValueError("Analyst SQL summary response missing analysis.")
        return analysis

    async def _synthesize_research(
        self,
        *,
        question: str,
        sources: list[dict[str, Any]],
        memory_context: str = "",
    ) -> dict[str, Any]:
        prompt = self._prompt(
            ANALYST_DEEP_RESEARCH_PROMPT.format(
                question=question,
                memory_context=memory_context,
                sources=json.dumps(sources, default=str),
            )
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=1200))
        if not isinstance(parsed.get("synthesis"), str):
            raise ValueError("Research LLM response missing synthesis.")
        findings = parsed.get("findings")
        if findings is not None and not isinstance(findings, list):
            raise ValueError("Research LLM response findings must be a list.")
        follow_ups = parsed.get("follow_ups")
        if follow_ups is not None and not isinstance(follow_ups, list):
            raise ValueError("Research LLM response follow_ups must be a list.")
        return parsed

    async def _run_web_search_if_needed(
        self,
        *,
        task: AgentTask,
        existing_sources: list[dict[str, Any]],
    ) -> WebSearchResult | None:
        if existing_sources and not task.input.get("force_web_search"):
            return None
        if not self._config.web_search_enabled:
            return None
        if self._web_search_tool is None:
            if task.input.get("force_web_search"):
                raise RuntimeError("Web search was forced, but no WebSearchTool is configured.")
            return None
        if not self._question_requests_web(task.question) and not task.input.get("force_web_search"):
            return None
        return await self._web_search_tool.search(task.question)

    def _collect_sources(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        explicit = context.get("sources")
        if isinstance(explicit, list):
            return [item for item in explicit if isinstance(item, dict)]

        sources: list[dict[str, Any]] = []
        for result in context.get("step_results", []):
            if not isinstance(result, dict):
                continue
            output = result.get("output")
            if not isinstance(output, dict):
                continue
            for key in ("sources", "results"):
                raw_items = output.get(key)
                if isinstance(raw_items, list):
                    sources.extend(item for item in raw_items if isinstance(item, dict))
        return sources

    def _requested_mode(self, task: AgentTask) -> AnalystAgentMode:
        return normalize_analyst_mode(
            task.input.get("agent_mode") or task.input.get("mode"),
            default=AnalystAgentMode.auto,
        ) or AnalystAgentMode.auto

    async def _select_execution_mode(self, task: AgentTask) -> dict[str, Any]:
        prompt = self._prompt(
            ANALYST_MODE_SELECTION_PROMPT.format(
                question=task.question,
                task_kind=task.task_kind.value,
                input_mode=str(task.input.get("agent_mode") or task.input.get("mode") or ""),
                scope=json.dumps(self.specification.metadata.get("scope") or {}, default=str, indent=2),
                sql_tools=json.dumps([tool.describe() for tool in self._initial_sql_tools()], default=str, indent=2),
                web_search_configured=self._web_search_tool is not None,
                has_result_context=isinstance(task.context.get("result"), dict),
                has_sources=bool(task.context.get("sources") or task.context.get("step_results")),
                memory_context=self._memory_context(task.context),
            )
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=500))
        raw_mode = str(parsed.get("agent_mode") or parsed.get("mode") or "").strip()
        if raw_mode == "clarify":
            parsed["agent_mode"] = "clarify"
            return parsed
        mode = normalize_analyst_mode(raw_mode)
        if mode is None or mode.value not in {item.value for item in self._supported_modes()}:
            raise ValueError(f"Analyst mode selection returned invalid mode: {mode}")
        parsed["agent_mode"] = mode.value
        return parsed

    def _supported_modes(self) -> list[AnalystAgentMode]:
        modes = [AnalystAgentMode.sql]
        if self._config.supports_research:
            modes.append(AnalystAgentMode.research)
        modes.append(AnalystAgentMode.context_analysis)
        return modes

    def _capabilities(self) -> list[str]:
        capabilities = ["governed analytics", "dataset-native SQL fallback"]
        if self._config.semantic_model_ids:
            capabilities.append("semantic-model analysis")
        if self._config.supports_research:
            capabilities.append("source-backed research")
        if self._config.web_search_enabled:
            capabilities.append("web search")
        if self._semantic_search_tools:
            capabilities.append("semantic grounding")
        capabilities.append(f"agent_modes: {', '.join(mode.value for mode in self._supported_modes())}")
        return capabilities

    def _constraints(self) -> list[str]:
        return [
            "Read-only analytical work only.",
            "No connector sync or mutation side effects.",
            f"semantic models: {', '.join(self._config.semantic_model_ids) or 'none'}",
            f"datasets: {', '.join(self._config.dataset_ids) or 'none'}",
            f"query policy: {self._config.query_policy}",
            f"web search: {'enabled' if self._config.web_search_enabled else 'disabled'}",
            f"web allowed domains: {', '.join(self._config.web_search_allowed_domains) or 'any'}",
        ]

    def _initial_sql_tools(self) -> list[SqlAnalysisTool]:
        semantic_tools = [tool for tool in self._sql_tools if tool.query_scope == SqlQueryScope.semantic]
        dataset_tools = [
            tool
            for tool in self._sql_tools
            if tool.query_scope == SqlQueryScope.dataset
            or (self._config.allow_source_scope and tool.query_scope == SqlQueryScope.source)
        ]
        if self._config.query_policy == "semantic_only":
            return semantic_tools
        if self._config.query_policy == "dataset_only":
            return dataset_tools
        if self._config.query_policy == "dataset_preferred":
            return [*dataset_tools, *[tool for tool in semantic_tools if tool not in dataset_tools]]
        return [*semantic_tools, *[tool for tool in dataset_tools if tool not in semantic_tools]]

    def _fallback_sql_tools(self, current_tool: SqlAnalysisTool) -> list[SqlAnalysisTool]:
        if current_tool.query_scope != SqlQueryScope.semantic:
            return []
        if self._config.query_policy == "semantic_only":
            return []
        return [
            tool
            for tool in self._sql_tools
            if tool is not current_tool
            and (
                tool.query_scope == SqlQueryScope.dataset
                or (self._config.allow_source_scope and tool.query_scope == SqlQueryScope.source)
            )
        ]

    def _sql_request(self, task: AgentTask) -> AnalystQueryRequest:
        return AnalystQueryRequest(
            question=task.question,
            conversation_context=self._combined_conversation_context(task.context),
            filters=task.context.get("filters"),
            limit=task.context.get("limit", 1000),
            error_retries=0,
            error_history=[],
        )

    def _classify_sql_failure(self, *, response: AnalystQueryResponse, tool: SqlAnalysisTool) -> SqlFailureTaxonomy:
        outcome = response.outcome
        if outcome is None:
            return SqlFailureTaxonomy(
                kind="unknown",
                status=None,
                stage=None,
                message=response.error,
                fallback_eligible=False,
            )
        message = response.error or outcome.message or outcome.original_error
        metadata = outcome.metadata if isinstance(outcome.metadata, dict) else {}
        failure_kind = str(metadata.get("semantic_failure_kind") or "").strip()
        fallback_eligible = self._is_semantic_scope_fallback_eligible(response=response, tool=tool)
        if fallback_eligible and failure_kind:
            kind = failure_kind
        elif fallback_eligible:
            kind = "semantic_scope_limit"
        elif outcome.status == AnalystOutcomeStatus.access_denied:
            kind = "access_denied"
        elif outcome.status == AnalystOutcomeStatus.invalid_request:
            kind = "invalid_request"
        elif outcome.status == AnalystOutcomeStatus.needs_clarification:
            kind = "needs_clarification"
        elif outcome.status == AnalystOutcomeStatus.empty_result:
            kind = "empty_result"
        elif outcome.status == AnalystOutcomeStatus.query_error:
            kind = "query_error"
        elif outcome.status == AnalystOutcomeStatus.execution_error:
            kind = "execution_error"
        else:
            kind = outcome.status.value
        return SqlFailureTaxonomy(
            kind=kind,
            status=outcome.status.value,
            stage=outcome.stage.value if outcome.stage is not None else None,
            message=message,
            fallback_eligible=fallback_eligible,
        )

    def _is_semantic_scope_fallback_eligible(self, *, response: AnalystQueryResponse, tool: SqlAnalysisTool) -> bool:
        outcome = response.outcome
        if outcome is None or tool.query_scope != SqlQueryScope.semantic:
            return False
        if outcome.status not in {AnalystOutcomeStatus.query_error, AnalystOutcomeStatus.execution_error}:
            return False
        if not self._fallback_sql_tools(tool):
            return False
        metadata = outcome.metadata if isinstance(outcome.metadata, dict) else {}
        if metadata.get("scope_fallback_eligible") is True:
            return True
        error_text = " ".join(
            part
            for part in (outcome.message, outcome.original_error, response.error)
            if isinstance(part, str) and part.strip()
        ).casefold()
        return any(marker in error_text for marker in _SEMANTIC_FALLBACK_MARKERS)

    def _apply_scope_fallback(
        self,
        *,
        fallback_response: AnalystQueryResponse,
        original_response: AnalystQueryResponse,
        from_tool: SqlAnalysisTool,
        to_tool: SqlAnalysisTool,
        taxonomy: SqlFailureTaxonomy,
    ) -> AnalystQueryResponse:
        original_outcome = original_response.outcome
        fallback_outcome = fallback_response.outcome
        if fallback_outcome is None:
            return fallback_response
        recovery_actions = list(fallback_outcome.recovery_actions)
        recovery_actions.append(
            AnalystRecoveryAction(
                action="fallback_query_scope",
                rationale=(
                    f"Fell back from {from_tool.query_scope.value} scope to {to_tool.query_scope.value} "
                    "after semantic execution feedback."
                ),
                details={
                    "from_scope": from_tool.query_scope.value,
                    "to_scope": to_tool.query_scope.value,
                    "from_tool": from_tool.name,
                    "to_tool": to_tool.name,
                    "reason": taxonomy.message,
                    "semantic_failure_kind": taxonomy.kind,
                },
            )
        )
        metadata = dict(fallback_outcome.metadata or {})
        metadata["semantic_failure"] = taxonomy.to_dict()
        updated_outcome = fallback_outcome.model_copy(
            update={
                "attempted_query_scope": from_tool.query_scope,
                "final_query_scope": to_tool.query_scope,
                "fallback_from_query_scope": from_tool.query_scope,
                "fallback_to_query_scope": to_tool.query_scope,
                "fallback_reason": taxonomy.message,
                "selected_semantic_model_id": (
                    original_outcome.selected_semantic_model_id
                    if original_outcome and original_outcome.selected_semantic_model_id
                    else fallback_outcome.selected_semantic_model_id
                ),
                "recovery_actions": recovery_actions,
                "metadata": metadata,
            }
        )
        return fallback_response.model_copy(update={"outcome": updated_outcome})

    def _build_sql_output(
        self,
        *,
        summary: str,
        response: AnalystQueryResponse,
        taxonomy: SqlFailureTaxonomy,
    ) -> dict[str, Any]:
        return {
            "analysis": summary,
            "result": response.result.model_dump(mode="json") if response.result else {},
            "analysis_path": response.analysis_path,
            "sql_canonical": response.sql_canonical,
            "sql_executable": response.sql_executable,
            "selected_datasets": [dataset.dataset_id for dataset in response.selected_datasets],
            "selected_semantic_models": (
                [response.selected_semantic_model_id] if response.selected_semantic_model_id else []
            ),
            "query_scope": response.query_scope.value if response.query_scope else None,
            "outcome": response.outcome.model_dump(mode="json") if response.outcome else None,
            "error_taxonomy": taxonomy.to_dict(),
        }

    @staticmethod
    def _result_status_for_sql(response: AnalystQueryResponse) -> AgentResultStatus:
        outcome = response.outcome
        if outcome is not None and outcome.status == AnalystOutcomeStatus.needs_clarification:
            return AgentResultStatus.needs_clarification
        if response.has_error:
            return AgentResultStatus.failed
        return AgentResultStatus.succeeded

    def _tool_specifications(self) -> list[AgentToolSpecification]:
        tools = [
            AgentToolSpecification(
                name=tool.name,
                description=tool.description or "Executes governed analytical SQL.",
                output_contract=AgentIOContract(required_keys=["result"]),
            )
            for tool in self._sql_tools
        ]
        if self._web_search_tool is not None:
            tools.append(
                AgentToolSpecification(
                    name="web-search",
                    description="Retrieves external evidence under analyst policy.",
                    output_contract=AgentIOContract(required_keys=["results"]),
                )
            )
        return tools

    def _prompt(self, base_prompt: str) -> str:
        sections = [base_prompt.strip()]
        if self._config.prompts.system_prompt:
            sections.append(f"Analyst system guidance:\n{self._config.prompts.system_prompt.strip()}")
        if self._config.prompts.user_prompt:
            sections.append(f"Analyst execution guidance:\n{self._config.prompts.user_prompt.strip()}")
        if self._config.prompts.response_format_prompt:
            sections.append(f"Analyst response format guidance:\n{self._config.prompts.response_format_prompt.strip()}")
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _memory_context(context: dict[str, Any]) -> str:
        value = context.get("memory_context")
        return value if isinstance(value, str) else ""

    @staticmethod
    def _combined_conversation_context(context: dict[str, Any]) -> str:
        parts = []
        conversation = context.get("conversation_context")
        if isinstance(conversation, str) and conversation.strip():
            parts.append(conversation.strip())
        memory = context.get("memory_context")
        if isinstance(memory, str) and memory.strip():
            parts.append("Memory:\n" + memory.strip())
        return "\n\n".join(parts)

    @staticmethod
    def _question_requests_web(question: str) -> bool:
        text = question.casefold()
        return any(
            cue in text
            for cue in ("search", "web", "latest", "current", "news", "source", "sources", "look up", "research")
        )

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("LLM response did not contain a JSON object.")
        parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("LLM response JSON must be an object.")
        return parsed


SemanticAnalystAgent = AnalystAgent

__all__ = ["AnalystAgent", "SemanticAnalystAgent"]
