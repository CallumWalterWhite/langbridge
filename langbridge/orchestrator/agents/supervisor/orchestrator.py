"""
Supervisor orchestrator that coordinates planner, analyst, research, and visual agents.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence

from orchestrator.llm.provider import LLMProvider
from orchestrator.agents.analyst import AnalystAgent
from orchestrator.agents.deep_research import DeepResearchAgent, DeepResearchResult
from orchestrator.agents.planner import (
    AgentName,
    Plan,
    PlanStep,
    PlannerRequest,
    PlanningAgent,
    PlanningConstraints,
    RouteName,
)
from orchestrator.agents.planner.router import _extract_signals
from orchestrator.agents.visual import VisualAgent
from orchestrator.agents.web_search import WebSearchAgent, WebSearchResult
from orchestrator.tools.sql_analyst.interfaces import AnalystQueryResponse


@dataclass
class OrchestrationContext:
    """Context passed into the supervisor to capture routing metadata."""

    analyst_tools: Sequence[Any]  # Retained for backwards compatibility / auditing
    trace_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanExecutionArtifacts:
    """Intermediate artefacts captured while executing a planner-generated workflow."""

    analyst_result: Optional[AnalystQueryResponse] = None
    data_payload: Dict[str, Any] = field(default_factory=dict)
    visualization: Dict[str, Any] = field(default_factory=dict)
    research_result: Optional[DeepResearchResult] = None
    web_search_result: Optional[WebSearchResult] = None
    clarifying_question: Optional[str] = None


@dataclass
class ReasoningDecision:
    """Outcome returned by the reasoning agent after each execution pass."""

    continue_planning: bool
    updated_context: Optional[Dict[str, Any]] = None
    rationale: Optional[str] = None


class ReasoningAgent:
    """Simple reasoning layer that decides whether additional planning is required."""

    def __init__(
        self,
        *,
        max_iterations: int = 2,
        llm: Optional[LLMProvider] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("ReasoningAgent requires at least one iteration.")
        self.max_iterations = max_iterations
        self.logger = logger or logging.getLogger(__name__)
        self.llm = llm

    @staticmethod
    def _has_structured_data(artifacts: PlanExecutionArtifacts) -> bool:
        return bool(artifacts.analyst_result and artifacts.analyst_result.result)

    @staticmethod
    def _has_web_results(artifacts: PlanExecutionArtifacts) -> bool:
        return bool(artifacts.web_search_result)

    @staticmethod
    def _has_research_results(artifacts: PlanExecutionArtifacts) -> bool:
        if not artifacts.research_result:
            return False
        return bool(artifacts.research_result.findings or artifacts.research_result.synthesis)

    @staticmethod
    def _is_low_signal_research(result: DeepResearchResult) -> bool:
        if not result.findings:
            return True
        if all(finding.source == "knowledge_base" for finding in result.findings):
            return True
        synthesis = (result.synthesis or "").lower()
        if "no documents provided" in synthesis or "reviewed 0 document" in synthesis:
            return True
        return False

    @staticmethod
    def _pick_fallback_route(current_route: Optional[str]) -> RouteName:
        if current_route == RouteName.WEB_SEARCH.value:
            return RouteName.DEEP_RESEARCH
        return RouteName.WEB_SEARCH

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
    def _coerce_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"true", "yes", "1"}:
                return True
            if cleaned in {"false", "no", "0"}:
                return False
        return None

    @staticmethod
    def _normalize_route_name(value: Any) -> Optional[RouteName]:
        if isinstance(value, RouteName):
            return value
        if value is None:
            return None
        cleaned = str(value).strip().lower()
        if not cleaned:
            return None
        for route in RouteName:
            if cleaned == route.value.lower() or cleaned == route.name.lower():
                return route
        alias_map = {
            "analyst": RouteName.SIMPLE_ANALYST,
            "simpleanalyst": RouteName.SIMPLE_ANALYST,
            "visual": RouteName.ANALYST_THEN_VISUAL,
            "chart": RouteName.ANALYST_THEN_VISUAL,
            "websearch": RouteName.WEB_SEARCH,
            "web": RouteName.WEB_SEARCH,
            "research": RouteName.DEEP_RESEARCH,
            "deepresearch": RouteName.DEEP_RESEARCH,
            "clarify": RouteName.CLARIFY,
        }
        return alias_map.get(cleaned)

    def _normalize_route_list(self, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, (list, tuple, set)):
            items = value
        else:
            items = [value]
        routes: list[str] = []
        for item in items:
            route = self._normalize_route_name(item)
            if route and route.value not in routes:
                routes.append(route.value)
        return routes

    def _summarize_artifacts(self, artifacts: PlanExecutionArtifacts) -> Dict[str, Any]:
        columns: list[Any] = []
        rows: list[Any] = []
        if artifacts.data_payload:
            columns = list(artifacts.data_payload.get("columns") or [])
            rows = list(artifacts.data_payload.get("rows") or [])
        elif artifacts.analyst_result and artifacts.analyst_result.result:
            columns = list(artifacts.analyst_result.result.columns or [])
            rows = list(artifacts.analyst_result.result.rows or [])

        analyst_error = artifacts.analyst_result.error if artifacts.analyst_result else None
        web_count = len(artifacts.web_search_result.results) if artifacts.web_search_result else 0
        research_findings = (
            len(artifacts.research_result.findings) if artifacts.research_result else 0
        )
        research_synthesis = (
            (artifacts.research_result.synthesis or "") if artifacts.research_result else ""
        )
        chart_type = None
        if isinstance(artifacts.visualization, dict):
            chart_type = artifacts.visualization.get("chart_type") or artifacts.visualization.get(
                "chartType"
            )

        return {
            "row_count": len(rows),
            "columns": columns,
            "analyst_error": analyst_error,
            "web_results_count": web_count,
            "research_findings_count": research_findings,
            "research_synthesis": research_synthesis[:240],
            "visualization_chart_type": chart_type,
        }

    def _build_llm_prompt(
        self,
        *,
        iteration: int,
        plan: Plan,
        artifacts: PlanExecutionArtifacts,
        diagnostics: Dict[str, Any],
        user_query: Optional[str],
    ) -> str:
        summary = self._summarize_artifacts(artifacts)
        prompt_sections = [
            "You are an orchestration evaluator. Decide if more planning is needed.",
            "Return ONLY JSON with keys: continue_planning (boolean), rationale (string).",
            "Optional keys: force_route, prefer_routes, avoid_routes, require_web_search,",
            "require_deep_research, require_visual, require_sql, retry_due_to_error,",
            "retry_due_to_empty, retry_due_to_low_sources.",
            "Routes: SimpleAnalyst, AnalystThenVisual, WebSearch, DeepResearch, Clarify.",
            f"User query: {user_query or ''}",
            f"Current route: {plan.route}",
            f"Iteration: {iteration + 1} of {self.max_iterations}",
            f"Execution summary (JSON): {json.dumps(summary, default=str, ensure_ascii=True)}",
            f"Diagnostics (JSON): {json.dumps(diagnostics or {}, default=str, ensure_ascii=True)}",
        ]
        return "\n".join(prompt_sections)

    def _evaluate_with_llm(
        self,
        *,
        iteration: int,
        plan: Plan,
        artifacts: PlanExecutionArtifacts,
        diagnostics: Dict[str, Any],
        user_query: Optional[str],
    ) -> Optional[ReasoningDecision]:
        if not self.llm:
            return None
        prompt = self._build_llm_prompt(
            iteration=iteration,
            plan=plan,
            artifacts=artifacts,
            diagnostics=diagnostics,
            user_query=user_query,
        )
        try:
            response = self.llm.complete(prompt, temperature=0.0, max_tokens=350)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("ReasoningAgent LLM evaluation failed: %s", exc)
            return None

        payload = self._parse_llm_payload(str(response))
        if not payload:
            return None

        continue_value = self._coerce_bool(payload.get("continue_planning"))
        if continue_value is None:
            return None

        rationale = str(payload.get("rationale") or "").strip() or "LLM evaluation completed."
        if not continue_value:
            return ReasoningDecision(continue_planning=False, rationale=rationale)

        reasoning_payload: Dict[str, Any] = {"previous_route": plan.route}
        force_route = self._normalize_route_name(payload.get("force_route") or payload.get("force_tool"))
        if force_route:
            reasoning_payload["force_route"] = force_route.value

        prefer_routes = self._normalize_route_list(payload.get("prefer_routes") or payload.get("preferred_routes"))
        if prefer_routes:
            reasoning_payload["prefer_routes"] = prefer_routes
        avoid_routes = self._normalize_route_list(payload.get("avoid_routes"))
        if avoid_routes:
            reasoning_payload["avoid_routes"] = avoid_routes

        require_web_search = self._coerce_bool(payload.get("require_web_search"))
        if require_web_search:
            reasoning_payload["require_web_search"] = True
        require_deep = self._coerce_bool(payload.get("require_deep_research"))
        if require_deep:
            reasoning_payload["require_deep_research"] = True
        require_visual = self._coerce_bool(payload.get("require_visual"))
        if require_visual:
            reasoning_payload["require_visual"] = True
        require_sql = self._coerce_bool(payload.get("require_sql"))
        if require_sql:
            reasoning_payload["require_sql"] = True

        for flag in ("retry_due_to_error", "retry_due_to_empty", "retry_due_to_low_sources"):
            flag_value = payload.get(flag)
            if flag_value is not None:
                reasoning_payload[flag] = flag_value

        return ReasoningDecision(
            continue_planning=True,
            updated_context={"reasoning": reasoning_payload},
            rationale=rationale,
        )

    def _apply_llm_safeguards(
        self,
        decision: ReasoningDecision,
        *,
        plan: Plan,
        artifacts: PlanExecutionArtifacts,
        user_query: Optional[str],
    ) -> ReasoningDecision:
        has_structured_data = self._has_structured_data(artifacts)
        has_web_results = self._has_web_results(artifacts)
        has_research = self._has_research_results(artifacts)
        has_data = has_structured_data or has_web_results or has_research

        analyst_error = artifacts.analyst_result and artifacts.analyst_result.error
        if not decision.continue_planning and analyst_error and not (has_web_results or has_research):
            force_route = self._pick_fallback_route(plan.route)
            rationale = "Retrying due to analyst error."
            self.logger.debug("%s Error: %s", rationale, artifacts.analyst_result.error)
            return self._build_retry_decision(
                plan=plan,
                rationale=rationale,
                force_route=force_route,
                retry_flag="retry_due_to_error",
                detail=str(artifacts.analyst_result.error),
            )

        if not decision.continue_planning and not has_data:
            force_route = self._pick_fallback_route(plan.route)
            rationale = "No structured or research data produced; requesting replanning."
            return self._build_retry_decision(
                plan=plan,
                rationale=rationale,
                force_route=force_route,
                retry_flag="retry_due_to_empty",
            )

        if not decision.continue_planning:
            return decision

        updated_context = decision.updated_context or {}
        reasoning_payload = updated_context.get("reasoning")
        if not isinstance(reasoning_payload, dict):
            reasoning_payload = {"previous_route": plan.route}
        else:
            reasoning_payload.setdefault("previous_route", plan.route)

        if not any(
            flag in reasoning_payload for flag in ("retry_due_to_error", "retry_due_to_empty", "retry_due_to_low_sources")
        ):
            if analyst_error and not (has_web_results or has_research):
                reasoning_payload["retry_due_to_error"] = str(analyst_error)
            elif not has_data:
                reasoning_payload["retry_due_to_empty"] = True
            elif artifacts.research_result and self._is_low_signal_research(artifacts.research_result):
                reasoning_payload["retry_due_to_low_sources"] = True

        updated_context["reasoning"] = reasoning_payload
        return ReasoningDecision(
            continue_planning=True,
            updated_context=updated_context,
            rationale=decision.rationale,
        )

    def _build_retry_decision(
        self,
        *,
        plan: Plan,
        rationale: str,
        force_route: RouteName,
        retry_flag: str,
        detail: Optional[str] = None,
    ) -> ReasoningDecision:
        self.logger.debug(rationale)
        reasoning_payload: Dict[str, Any] = {
            "force_route": force_route.value,
            "previous_route": plan.route,
        }
        reasoning_payload[retry_flag] = detail if detail is not None else True
        return ReasoningDecision(
            continue_planning=True,
            updated_context={
                "reasoning": reasoning_payload
            },
            rationale=rationale,
        )

    def evaluate(
        self,
        *,
        iteration: int,
        plan: Plan,
        artifacts: PlanExecutionArtifacts,
        diagnostics: Dict[str, Any],
        user_query: Optional[str] = None,
    ) -> ReasoningDecision:
        if artifacts.clarifying_question:
            rationale = "Clarification needed from user; stopping further planning."
            self.logger.debug(rationale)
            return ReasoningDecision(continue_planning=False, rationale=rationale)

        if iteration + 1 >= self.max_iterations:
            rationale = "Max reasoning iterations reached; finalising current response."
            self.logger.debug(rationale)
            return ReasoningDecision(continue_planning=False, rationale=rationale)

        llm_decision = self._evaluate_with_llm(
            iteration=iteration,
            plan=plan,
            artifacts=artifacts,
            diagnostics=diagnostics,
            user_query=user_query,
        )
        if llm_decision:
            return self._apply_llm_safeguards(
                llm_decision,
                plan=plan,
                artifacts=artifacts,
                user_query=user_query,
            )

        has_structured_data = self._has_structured_data(artifacts)
        has_web_results = self._has_web_results(artifacts)
        has_research = self._has_research_results(artifacts)
        has_data = has_structured_data or has_web_results or has_research

        analyst_error = artifacts.analyst_result and artifacts.analyst_result.error
        if analyst_error and not (has_web_results or has_research):
            force_route = self._pick_fallback_route(plan.route)
            rationale = "Retrying due to analyst error."
            self.logger.debug("%s Error: %s", rationale, artifacts.analyst_result.error)
            return self._build_retry_decision(
                plan=plan,
                rationale=rationale,
                force_route=force_route,
                retry_flag="retry_due_to_error",
                detail=str(artifacts.analyst_result.error),
            )

        if not has_data:
            force_route = self._pick_fallback_route(plan.route)
            rationale = "No structured or research data produced; requesting replanning."
            return self._build_retry_decision(
                plan=plan,
                rationale=rationale,
                force_route=force_route,
                retry_flag="retry_due_to_empty",
            )

        signals = _extract_signals(user_query) if user_query else None

        if has_web_results and not has_research:
            has_sources = bool(artifacts.web_search_result and artifacts.web_search_result.results)
            if has_sources and (signals is None or signals.has_research_signals):
                rationale = "Web search produced sources; synthesizing with deep research."
                self.logger.debug(rationale)
                web_docs = artifacts.web_search_result.to_documents() if artifacts.web_search_result else []
                return ReasoningDecision(
                    continue_planning=True,
                    updated_context={
                        "documents": web_docs,
                        "reasoning": {
                            "force_route": RouteName.DEEP_RESEARCH.value,
                            "previous_route": plan.route,
                            "promoted_from_web_search": True,
                        },
                    },
                    rationale=rationale,
                )

        if has_research and not has_web_results:
            if artifacts.research_result and self._is_low_signal_research(artifacts.research_result):
                rationale = "Research lacked source material; broadening with web search."
                self.logger.debug(rationale)
                return ReasoningDecision(
                    continue_planning=True,
                    updated_context={
                        "reasoning": {
                            "force_route": RouteName.WEB_SEARCH.value,
                            "previous_route": plan.route,
                            "retry_due_to_low_sources": True,
                        }
                    },
                    rationale=rationale,
                )

        self.logger.debug("Reasoning agent determined results look sufficient.")
        return ReasoningDecision(continue_planning=False, rationale="Results look sufficient.")


class SupervisorOrchestrator:
    """High-level orchestrator routing between planner, analyst, research, and visual agents."""

    def __init__(
        self,
        *,
        visual_agent: VisualAgent,
        analyst_agent: Optional[AnalystAgent] = None,
        logger: Optional[logging.Logger] = None,
        planning_agent: Optional[PlanningAgent] = None,
        deep_research_agent: Optional[DeepResearchAgent] = None,
        web_search_agent: Optional[WebSearchAgent] = None,
        reasoning_agent: Optional[ReasoningAgent] = None,
    ) -> None:
        self.analyst_agent = analyst_agent
        self.visual_agent = visual_agent
        self.logger = logger or logging.getLogger(__name__)
        self.planning_agent = planning_agent or PlanningAgent()
        self.deep_research_agent = deep_research_agent or DeepResearchAgent(logger=self.logger)
        self.web_search_agent = web_search_agent or WebSearchAgent(logger=self.logger)
        self.reasoning_agent = reasoning_agent or ReasoningAgent(logger=self.logger)

    async def handle(
        self,
        user_query: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        title: Optional[str] = None,
        planning_constraints: Optional[PlanningConstraints] = None,
        planning_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute planner-driven workflows for a single user query."""

        start = time.perf_counter()

        plan: Optional[Plan] = None
        artifacts: Optional[PlanExecutionArtifacts] = None
        combined_artifacts = PlanExecutionArtifacts()
        final_decision: Optional[ReasoningDecision] = None
        extra_context: Dict[str, Any] = dict(planning_context or {})
        iteration_diagnostics: Dict[str, Any] = {}
        iterations_completed = 0

        for iteration in range(self.reasoning_agent.max_iterations):
            planner_request = self._build_planner_request(
                user_query,
                filters=filters,
                limit=limit,
                title=title,
                extra_context=extra_context,
                constraints=planning_constraints,
            )
            plan = self.planning_agent.plan(planner_request)
            artifacts = await self._execute_plan(
                plan,
                user_query=user_query,
                filters=filters,
                limit=limit,
                title=title,
            )
            self._merge_artifacts(combined_artifacts, artifacts)

            iteration_diagnostics = {
                "iteration": iteration,
                "plan_route": plan.route,
                "extra_context": extra_context,
            }
            final_decision = self.reasoning_agent.evaluate(
                iteration=iteration,
                plan=plan,
                artifacts=artifacts,
                diagnostics=iteration_diagnostics,
                user_query=user_query,
            )
            iterations_completed = iteration + 1

            if not final_decision.continue_planning:
                break

            extra_context = self._merge_context(extra_context, final_decision.updated_context or {})
        else:
            # Loop exhausted without final decision; treat last pass as final.
            self.logger.warning("Reasoning agent exhausted max iterations without convergence.")
            if not final_decision or final_decision.continue_planning:
                final_decision = ReasoningDecision(
                    continue_planning=False,
                    rationale="Max iterations reached without convergence.",
                )

        if plan is None or artifacts is None:
            raise RuntimeError("Planner did not produce a plan or artifacts.")

        analyst_result = artifacts.analyst_result or self._build_empty_analyst_response(
            error_message=artifacts.clarifying_question
            or "Planner route completed without invoking analyst agent.",
        )
        data_payload = artifacts.data_payload
        if not data_payload and artifacts.research_result:
            data_payload = self._coerce_research_payload(artifacts.research_result)
        visualization = artifacts.visualization

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        diagnostics: Dict[str, Any] = {
            "execution_time_ms": analyst_result.execution_time_ms,
            "total_elapsed_ms": elapsed_ms,
            "sql_executable": analyst_result.sql_executable,
            "sql_canonical": analyst_result.sql_canonical,
            "error": analyst_result.error,
            "dialect": analyst_result.dialect,
            "plan": plan.model_dump(),
        }
        if artifacts.research_result:
            diagnostics["research"] = artifacts.research_result.to_dict()
        web_search_result = artifacts.web_search_result or combined_artifacts.web_search_result
        if web_search_result:
            diagnostics["web_search"] = web_search_result.to_dict()
        if artifacts.clarifying_question:
            diagnostics["clarifying_question"] = artifacts.clarifying_question
        diagnostics["reasoning"] = {
            "iterations": iterations_completed,
            "final_rationale": final_decision.rationale if final_decision else None,
        }

        self.logger.info(
            "Planner route '%s' completed in %sms for query '%s'",
            plan.route,
            elapsed_ms,
            user_query,
        )

        return {
            "sql_canonical": analyst_result.sql_canonical,
            "sql_executable": analyst_result.sql_executable,
            "dialect": analyst_result.dialect,
            "model": analyst_result.model_name,
            "result": data_payload,
            "visualization": visualization,
            "diagnostics": diagnostics,
        }

    def _build_planner_request(
        self,
        user_query: str,
        *,
        filters: Optional[Dict[str, Any]],
        limit: Optional[int],
        title: Optional[str],
        extra_context: Optional[Dict[str, Any]] = None,
        constraints: Optional[PlanningConstraints] = None,
    ) -> PlannerRequest:
        context: Dict[str, Any] = {}
        if filters is not None:
            context["filters"] = filters
        if limit is not None:
            context["limit"] = limit
        if title:
            context["title"] = title
        if extra_context:
            context.update(extra_context)
        return PlannerRequest(
            question=user_query,
            context=context or None,
            constraints=constraints or PlanningConstraints(),
        )

    async def _execute_plan(
        self,
        plan: Plan,
        *,
        user_query: str,
        filters: Optional[Dict[str, Any]],
        limit: Optional[int],
        title: Optional[str],
    ) -> PlanExecutionArtifacts:
        artifacts = PlanExecutionArtifacts()
        step_outputs: Dict[str, Dict[str, Any]] = {}

        for step in plan.steps:
            agent_name = step.agent

            if agent_name == AgentName.ANALYST.value:
                analyst_result, data_payload = await self._run_analyst_step(
                    step,
                    user_query=user_query,
                    default_filters=filters,
                    default_limit=limit,
                )
                artifacts.analyst_result = analyst_result
                if data_payload:
                    artifacts.data_payload = data_payload
                step_outputs[step.id] = {
                    "agent": AgentName.ANALYST.value,
                    "analyst_result": analyst_result,
                    "data_payload": data_payload,
                }
                continue

            if agent_name == AgentName.VISUAL.value:
                visualization = self._run_visual_step(
                    step,
                    user_query=user_query,
                    title=title,
                    fallback_payload=artifacts.data_payload,
                    step_outputs=step_outputs,
                )
                artifacts.visualization = visualization
                step_outputs[step.id] = {
                    "agent": AgentName.VISUAL.value,
                    "visualization": visualization,
                }
                continue

            if agent_name == AgentName.DOC_RETRIEVAL.value:
                research_result = await self._run_doc_retrieval_step(step, user_query, step_outputs)
                artifacts.research_result = research_result
                step_outputs[step.id] = {
                    "agent": AgentName.DOC_RETRIEVAL.value,
                    "research_result": research_result,
                }
                if not artifacts.data_payload:
                    artifacts.data_payload = research_result.to_tabular()
                continue

            if agent_name == AgentName.WEB_SEARCH.value:
                web_search_result = await self._run_web_search_step(step, user_query)
                artifacts.web_search_result = web_search_result
                step_outputs[step.id] = {
                    "agent": AgentName.WEB_SEARCH.value,
                    "web_search_result": web_search_result,
                    "documents": web_search_result.to_documents(),
                }
                if not artifacts.data_payload:
                    artifacts.data_payload = web_search_result.to_tabular()
                continue

            if agent_name == AgentName.CLARIFY.value:
                artifacts.clarifying_question = step.input.get("clarifying_question")
                self.logger.info("Planner requested clarification: %s", artifacts.clarifying_question)
                break

            self.logger.warning("Unsupported agent '%s' in plan; skipping step.", agent_name)

        return artifacts

    async def _run_analyst_step(
        self,
        step: PlanStep,
        *,
        user_query: str,
        default_filters: Optional[Dict[str, Any]],
        default_limit: Optional[int],
    ) -> tuple[AnalystQueryResponse, Dict[str, Any]]:
        if not self.analyst_agent:
            raise RuntimeError("AnalystAgent is not configured but planner requested SQL analysis.")
        question = step.input.get("question") or user_query
        context_overrides = step.input.get("context") or {}
        step_filters = context_overrides.get("filters", default_filters)
        step_limit = context_overrides.get("limit", default_limit)
        conversation_context = context_overrides.get("conversation_context")
        
        analyst_result: AnalystQueryResponse = await self.analyst_agent.answer_async(
            question,
            conversation_context=conversation_context,
            filters=step_filters,
            limit=step_limit,
        )
        data_payload = self._extract_data_payload(analyst_result)
        return analyst_result, data_payload

    def _run_visual_step(
        self,
        step: PlanStep,
        *,
        user_query: str,
        title: Optional[str],
        fallback_payload: Dict[str, Any],
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        reference_id = step.input.get("rows_ref")
        referenced_payload = self._resolve_rows_reference(reference_id, step_outputs)
        data = referenced_payload or fallback_payload or {"columns": [], "rows": []}
        viz_title = title or f"Visualization for '{user_query}'"
        user_intent = step.input.get("user_intent")
        return self.visual_agent.run(
            data,
            title=viz_title,
            question=user_query,
            user_intent=user_intent,
        )

    async def _run_doc_retrieval_step(
        self,
        step: PlanStep,
        user_query: str,
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> DeepResearchResult:
        if not self.deep_research_agent:
            raise RuntimeError("DeepResearchAgent is not configured but planner requested DocRetrieval.")
        context = step.input.get("context") or {}
        source_step_ref = step.input.get("source_step_ref")
        if source_step_ref:
            documents = self._resolve_documents_reference(source_step_ref, step_outputs)
            if documents:
                context = self._merge_document_context(context, documents)
        timebox = int(step.input.get("timebox_seconds", 30))
        question = step.input.get("question") or user_query
        return await self.deep_research_agent.research_async(
            question=question,
            context=context,
            timebox_seconds=timebox,
        )

    async def _run_web_search_step(self, step: PlanStep, user_query: str) -> WebSearchResult:
        if not self.web_search_agent:
            raise RuntimeError("WebSearchAgent is not configured but planner requested WebSearch.")
        query = step.input.get("query") or user_query
        context = step.input.get("context") or {}
        max_results = step.input.get("max_results", 6)
        region = step.input.get("region") or context.get("region")
        safe_search = step.input.get("safe_search") or context.get("safe_search")
        timebox = int(step.input.get("timebox_seconds", 10))
        try:
            max_results_value = int(max_results)
        except (TypeError, ValueError):
            max_results_value = 6

        return await self.web_search_agent.search_async(
            query,
            max_results=max_results_value,
            region=region,
            safe_search=safe_search,
            timebox_seconds=timebox,
        )

    @staticmethod
    def _extract_data_payload(analyst_result: AnalystQueryResponse) -> Dict[str, Any]:
        if analyst_result.result:
            return {
                "columns": analyst_result.result.columns,
                "rows": analyst_result.result.rows,
            }
        return {}

    @staticmethod
    def _merge_artifacts(base: PlanExecutionArtifacts, updates: PlanExecutionArtifacts) -> None:
        if updates.analyst_result:
            base.analyst_result = updates.analyst_result
        if updates.data_payload:
            base.data_payload = updates.data_payload
        if updates.visualization:
            base.visualization = updates.visualization
        if updates.research_result:
            base.research_result = updates.research_result
        if updates.web_search_result:
            base.web_search_result = updates.web_search_result
        if updates.clarifying_question:
            base.clarifying_question = updates.clarifying_question

    @staticmethod
    def _merge_context(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        if not updates:
            return dict(base)
        merged = dict(base)
        for key, value in updates.items():
            if key == "reasoning" and isinstance(value, dict):
                existing = merged.get("reasoning")
                if isinstance(existing, dict):
                    merged["reasoning"] = {**existing, **value}
                else:
                    merged["reasoning"] = dict(value)
                continue
            if key == "documents" and isinstance(value, list):
                existing = merged.get("documents")
                if isinstance(existing, list):
                    merged["documents"] = existing + [doc for doc in value if doc not in existing]
                elif isinstance(existing, dict):
                    merged["documents"] = [existing] + list(value)
                else:
                    merged["documents"] = list(value)
                continue
            merged[key] = value
        return merged

    @staticmethod
    def _coerce_research_payload(result: DeepResearchResult) -> Dict[str, Any]:
        return result.to_tabular()

    @staticmethod
    def _merge_document_context(
        context: Dict[str, Any],
        documents: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        merged = dict(context)
        cleaned_docs = [doc for doc in documents if isinstance(doc, dict)]
        if not cleaned_docs:
            return merged
        existing = merged.get("documents")
        if isinstance(existing, list):
            merged["documents"] = existing + [doc for doc in cleaned_docs if doc not in existing]
        elif isinstance(existing, dict):
            merged["documents"] = [existing] + cleaned_docs
        else:
            merged["documents"] = cleaned_docs
        return merged

    @staticmethod
    def _resolve_rows_reference(
        reference_id: Optional[str],
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not reference_id:
            return None
        referenced = step_outputs.get(reference_id)
        if not referenced:
            return None
        if "data_payload" in referenced:
            return referenced["data_payload"]
        if "research_result" in referenced:
            research_result: DeepResearchResult = referenced["research_result"]
            return research_result.to_tabular()
        return None

    @staticmethod
    def _resolve_documents_reference(
        reference_id: Optional[str],
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> Optional[Sequence[Dict[str, Any]]]:
        if not reference_id:
            return None
        referenced = step_outputs.get(reference_id)
        if not referenced:
            return None
        documents = referenced.get("documents")
        if isinstance(documents, list):
            return [doc for doc in documents if isinstance(doc, dict)]
        web_search_result = referenced.get("web_search_result")
        if isinstance(web_search_result, WebSearchResult):
            return web_search_result.to_documents()
        return None

    @staticmethod
    def _build_empty_analyst_response(*, error_message: str) -> AnalystQueryResponse:
        return AnalystQueryResponse(
            sql_canonical="",
            sql_executable="",
            dialect="n/a",
            model_name="",
            result=None,
            error=error_message,
            execution_time_ms=None,
        )


__all__ = ["OrchestrationContext", "SupervisorOrchestrator"]
