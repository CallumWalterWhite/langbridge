"""Mode-based analyst agent for Langbridge AI."""

from __future__ import annotations

import json
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
from langbridge.ai.agents.analyst.prompts import (
    ANALYST_CONTEXT_ANALYSIS_PROMPT,
    ANALYST_DEEP_RESEARCH_PROMPT,
    ANALYST_MODE_SELECTION_PROMPT,
    ANALYST_SQL_RESPONSE_PROMPT,
    ANALYST_SQL_TOOL_SELECTION_PROMPT,
)
from langbridge.ai.llm.base import LLMProvider
from langbridge.ai.profiles import AnalystAgentScope
from langbridge.ai.tools.semantic_search import SemanticSearchTool
from langbridge.ai.tools.sql import SqlAnalysisTool
from langbridge.ai.tools.sql.interfaces import AnalystQueryRequest, AnalystQueryResponse
from langbridge.ai.tools.web_search import WebSearchResult, WebSearchTool


class AnalystAgent(BaseAgent):
    """Performs governed analytics and research through configured tools."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        scope: AnalystAgentScope | None = None,
        sql_analysis_tools: Sequence[SqlAnalysisTool] | None = None,
        semantic_search_tools: Sequence[SemanticSearchTool] | None = None,
        web_search_tool: WebSearchTool | None = None,
    ) -> None:
        self._llm = llm_provider
        self._scope = scope or AnalystAgentScope()
        self._sql_tools = list(sql_analysis_tools or [])
        self._semantic_search_tools = list(semantic_search_tools or [])
        self._web_search_tool = web_search_tool

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name=self._scope.agent_name,
            description=self._scope.description
            or "Answers governed analytics and research questions with configured Langbridge tools.",
            task_kinds=self._task_kinds(),
            capabilities=[
                f"modes: {', '.join(self._scope.enabled_modes)}",
                "semantic analysis",
                "dataset analysis",
                "federated SQL analysis",
                *(["deep research synthesis"] if self._scope.supports_research else []),
                *(["web-backed research"] if self._scope.web_search_enabled else []),
            ],
            constraints=[
                "Read-only analytical work only.",
                "No connector sync or mutation side effects.",
                f"semantic models: {', '.join(self._scope.semantic_model_ids) or 'none'}",
                f"datasets: {', '.join(self._scope.dataset_ids) or 'none'}",
                f"web search: {'enabled' if self._scope.web_search_enabled else 'disabled'}",
                f"web allowed domains: {', '.join(self._scope.web_search_allowed_domains) or 'any'}",
                f"web denied domains: {', '.join(self._scope.web_search_denied_domains) or 'none'}",
            ],
            routing=AgentRoutingSpec(
                keywords=[
                    "metric",
                    "metrics",
                    "revenue",
                    "orders",
                    "customers",
                    "dataset",
                    "semantic",
                    "sql",
                    "trend",
                    "region",
                    "table",
                    "rows",
                    *(["research", "sources", "evidence", "synthesis"] if self._scope.supports_research else []),
                    *(["latest", "current", "search", "web", "news"] if self._scope.web_search_enabled else []),
                    *self._scope.routing_terms,
                ],
                phrases=[
                    "by region",
                    "by month",
                    "semantic model",
                    "show me",
                    *(["deep research", "multiple sources"] if self._scope.supports_research else []),
                    *(["search the web", "find sources", "look up"] if self._scope.web_search_enabled else []),
                    *self._scope.routing_phrases,
                ],
                direct_threshold=2,
                planner_threshold=1,
            ),
            output_contract=AgentIOContract(
                required_keys=["analysis", "result"],
                optional_keys=[
                    "sql_canonical",
                    "sql_executable",
                    "selected_datasets",
                    "selected_semantic_models",
                    "query_scope",
                    "synthesis",
                    "findings",
                    "sources",
                    "follow_ups",
                ],
            ),
            tools=self._tool_specifications(),
            cost_level=AgentCostLevel.high if self._scope.supports_research else AgentCostLevel.medium,
            metadata={"scope": self._scope.model_dump(mode="json")},
        )

    async def execute(self, task: AgentTask) -> AgentResult:
        if not task.question.strip():
            return self.build_result(
                task=task,
                status=AgentResultStatus.needs_clarification,
                error="Question is required for analyst work.",
            )
        if task.task_kind == AgentTaskKind.deep_research or self._requested_research_mode(task):
            return await self._execute_research(task)
        decision = await self._select_execution_mode(task)
        mode = str(decision.get("mode") or "").strip()
        if mode == "clarify":
            return self.build_result(
                task=task,
                status=AgentResultStatus.needs_clarification,
                error=str(decision.get("clarification_question") or decision.get("reason") or "Clarification needed."),
                diagnostics={"mode_decision": decision},
            )
        if mode == "deep_research":
            return await self._execute_research(task)
        if mode == "sql":
            if not self._sql_tools:
                return self.build_result(
                    task=task,
                    status=AgentResultStatus.blocked,
                    error="Analyst mode selected SQL, but no SQL analysis tools are configured.",
                    diagnostics={"mode_decision": decision},
                )
            return await self._execute_sql(task, mode_decision=decision)
        if mode == "context_analysis":
            return await self._execute_llm_analysis(task, mode_decision=decision)
        raise ValueError(f"Analyst mode selection returned unsupported mode: {mode}")

    async def _execute_sql(self, task: AgentTask, *, mode_decision: dict[str, Any] | None = None) -> AgentResult:
        tool = await self._select_sql_tool(task.question)
        response = await tool.arun(
            AnalystQueryRequest(
                question=task.question,
                conversation_context=task.context.get("conversation_context"),
                filters=task.context.get("filters"),
                limit=task.context.get("limit", 1000),
            )
        )
        summary = await self._summarize_sql_response(question=task.question, response=response)
        output = {
            "analysis": summary,
            "result": response.result.model_dump(mode="json") if response.result else {},
            "sql_canonical": response.sql_canonical,
            "sql_executable": response.sql_executable,
            "selected_datasets": [dataset.dataset_id for dataset in response.selected_datasets],
            "selected_semantic_models": (
                [response.selected_semantic_model_id] if response.selected_semantic_model_id else []
            ),
            "query_scope": response.query_scope.value if response.query_scope else None,
            "outcome": response.outcome.model_dump(mode="json") if response.outcome else None,
        }
        status = AgentResultStatus.failed if response.has_error else AgentResultStatus.succeeded
        return self.build_result(
            task=task,
            status=status,
            output=output,
            diagnostics={"tool": tool.name, "mode": "sql", "mode_decision": mode_decision or {}},
            error=response.error if response.has_error else None,
        )

    async def _execute_research(self, task: AgentTask) -> AgentResult:
        if not self._scope.supports_research:
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                error="Deep research is not enabled for this analyst scope.",
            )
        sources = self._collect_sources(task.context)
        web_result = await self._run_web_search_if_needed(task=task, existing_sources=sources)
        if web_result is not None:
            sources.extend([item.to_dict() for item in web_result.results])
        sources = sources[: self._scope.max_sources]
        if self._scope.require_sources and not sources:
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                output={"analysis": "", "result": {}, "synthesis": "", "findings": [], "sources": []},
                error="Research scope requires sources, but no evidence was available.",
                diagnostics={"mode": "deep_research"},
            )
        research = await self._synthesize_research(question=task.question, sources=sources)
        output = {
            "analysis": research["synthesis"],
            "result": {},
            "synthesis": research["synthesis"],
            "findings": research.get("findings", []),
            "sources": sources,
            "follow_ups": research.get("follow_ups", []),
            "selected_datasets": list(self._scope.dataset_ids),
            "selected_semantic_models": list(self._scope.semantic_model_ids),
            "query_scope": self._scope.query_scope_policy,
        }
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output=output,
            diagnostics={
                "mode": "deep_research",
                "web_search": web_result.to_dict() if web_result else None,
            },
        )

    async def _execute_llm_analysis(
        self,
        task: AgentTask,
        *,
        mode_decision: dict[str, Any] | None = None,
    ) -> AgentResult:
        context_result = task.context.get("result")
        if not isinstance(context_result, dict):
            return self.build_result(
                task=task,
                status=AgentResultStatus.blocked,
                error="No SQL tool or structured result context is available for analyst execution.",
            )
        prompt = ANALYST_CONTEXT_ANALYSIS_PROMPT.format(
            question=task.question,
            result=json.dumps(context_result, default=str),
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=800))
        result = parsed.get("result")
        if not isinstance(result, dict):
            raise ValueError("Analyst LLM response missing object field: result.")
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"analysis": str(parsed.get("analysis") or ""), "result": result},
            diagnostics={"mode": "context_analysis", "mode_decision": mode_decision or {}},
        )

    async def _select_sql_tool(self, question: str) -> SqlAnalysisTool:
        if len(self._sql_tools) == 1:
            return self._sql_tools[0]
        prompt = ANALYST_SQL_TOOL_SELECTION_PROMPT.format(
            question=question,
            filters="{}",
            tools=json.dumps([tool.describe() for tool in self._sql_tools], default=str, indent=2),
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=400))
        selected_name = str(parsed.get("tool_name") or "").strip()
        for tool in self._sql_tools:
            if tool.name == selected_name:
                return tool
        raise ValueError(f"LLM selected unknown SQL analysis tool: {selected_name}")

    async def _summarize_sql_response(self, *, question: str, response: AnalystQueryResponse) -> str:
        prompt = ANALYST_SQL_RESPONSE_PROMPT.format(
            question=question,
            sql=response.sql_canonical,
            result=json.dumps(response.result.model_dump(mode="json") if response.result else {}, default=str),
            outcome=json.dumps(response.outcome.model_dump(mode="json") if response.outcome else {}, default=str),
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=700))
        analysis = str(parsed.get("analysis") or "").strip()
        if not analysis:
            raise ValueError("Analyst SQL summary response missing analysis.")
        return analysis

    async def _synthesize_research(self, *, question: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = ANALYST_DEEP_RESEARCH_PROMPT.format(
            question=question,
            sources=json.dumps(sources, default=str),
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
        if not self._scope.web_search_enabled:
            return None
        if self._web_search_tool is None:
            if self._scope.web_search_provider_required or task.input.get("force_web_search"):
                raise RuntimeError("Web search is enabled, but no WebSearchTool is configured.")
            return None
        if not self._question_requests_web(task.question) and not task.input.get("force_web_search"):
            return None
        return await self._web_search_tool.search(task.question)

    def _collect_sources(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        explicit = context.get("sources")
        if isinstance(explicit, list):
            return [item for item in explicit if isinstance(item, dict)]

        sources: list[dict[str, Any]] = []
        allowed_agents = set(self._scope.allowed_evidence_agents)
        for result in context.get("step_results", []):
            if not isinstance(result, dict):
                continue
            if allowed_agents and str(result.get("agent_name") or "") not in allowed_agents:
                continue
            output = result.get("output")
            if not isinstance(output, dict):
                continue
            for item in output.get("results", []):
                if isinstance(item, dict):
                    sources.append(item)
        return sources

    def _requested_research_mode(self, task: AgentTask) -> bool:
        mode = str(task.input.get("mode") or task.context.get("mode") or "quick")
        return mode in {"research", "deep_research", "hybrid"} and self._scope.supports_research

    async def _select_execution_mode(self, task: AgentTask) -> dict[str, Any]:
        prompt = ANALYST_MODE_SELECTION_PROMPT.format(
            question=task.question,
            task_kind=task.task_kind.value,
            input_mode=str(task.input.get("mode") or ""),
            scope=json.dumps(self._scope.model_dump(mode="json"), default=str, indent=2),
            sql_tools=json.dumps([tool.describe() for tool in self._sql_tools], default=str, indent=2),
            semantic_search_tools=json.dumps([{"name": tool.name} for tool in self._semantic_search_tools], indent=2),
            web_search_configured=self._web_search_tool is not None,
            has_result_context=isinstance(task.context.get("result"), dict),
            has_sources=bool(task.context.get("sources") or task.context.get("step_results")),
        )
        parsed = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=500))
        mode = str(parsed.get("mode") or "").strip()
        if mode not in {"sql", "context_analysis", "deep_research", "clarify"}:
            raise ValueError(f"Analyst mode selection returned invalid mode: {mode}")
        return parsed

    def _task_kinds(self) -> list[AgentTaskKind]:
        kinds = [AgentTaskKind.analyst, AgentTaskKind.semantic_analysis]
        if self._scope.supports_research:
            kinds.append(AgentTaskKind.deep_research)
        return kinds

    def _tool_specifications(self) -> list[AgentToolSpecification]:
        specs = [
            AgentToolSpecification(
                name=tool.name,
                description=tool.description or "Executes governed SQL analysis.",
                output_contract=AgentIOContract(required_keys=["result"]),
            )
            for tool in self._sql_tools
        ]
        specs.extend(
            AgentToolSpecification(
                name=tool.name,
                description="Provides semantic/vector grounding for analyst work.",
            )
            for tool in self._semantic_search_tools
        )
        if self._web_search_tool is not None:
            specs.append(
                AgentToolSpecification(
                    name="web-search",
                    description="Retrieves external source evidence under analyst policy.",
                    output_contract=AgentIOContract(required_keys=["results"]),
                )
            )
        return specs

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
