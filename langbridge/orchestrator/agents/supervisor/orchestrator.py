"""
Supervisor orchestrator that coordinates planner, analyst, research, and visual agents.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence

from orchestrator.agents.analyst import AnalystAgent
from orchestrator.agents.deep_research import DeepResearchAgent, DeepResearchResult
from orchestrator.agents.planner import (
    AgentName,
    Plan,
    PlanStep,
    PlannerRequest,
    PlanningAgent,
    PlanningConstraints,
)
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
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("ReasoningAgent requires at least one iteration.")
        self.max_iterations = max_iterations
        self.logger = logger or logging.getLogger(__name__)

    def evaluate(
        self,
        *,
        iteration: int,
        plan: Plan,
        artifacts: PlanExecutionArtifacts,
        diagnostics: Dict[str, Any],
    ) -> ReasoningDecision:
        if artifacts.clarifying_question:
            rationale = "Clarification needed from user; stopping further planning."
            self.logger.debug(rationale)
            return ReasoningDecision(continue_planning=False, rationale=rationale)

        if iteration + 1 >= self.max_iterations:
            rationale = "Max reasoning iterations reached; finalising current response."
            self.logger.debug(rationale)
            return ReasoningDecision(continue_planning=False, rationale=rationale)

        analyst_error = artifacts.analyst_result and artifacts.analyst_result.error
        if analyst_error:
            rationale = "Retrying due to analyst error."
            self.logger.debug("%s Error: %s", rationale, artifacts.analyst_result.error)
            return ReasoningDecision(
                continue_planning=True,
                updated_context={
                    "reasoning": {
                        "retry_due_to_error": str(artifacts.analyst_result.error),
                        "previous_route": plan.route,
                    }
                },
                rationale=rationale,
            )

        has_data = bool(artifacts.data_payload) or bool(artifacts.research_result) or bool(
            artifacts.web_search_result
        )
        if not has_data:
            rationale = "No structured or research data produced; requesting replanning."
            self.logger.debug(rationale)
            return ReasoningDecision(
                continue_planning=True,
                updated_context={
                    "reasoning": {
                        "retry_due_to_empty": True,
                        "previous_route": plan.route,
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
        analyst_agent: AnalystAgent,
        visual_agent: VisualAgent,
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
            )
            iterations_completed = iteration + 1

            if not final_decision.continue_planning:
                break

            extra_context = {**extra_context, **(final_decision.updated_context or {})}
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
            "error": analyst_result.error,
            "dialect": analyst_result.dialect,
            "plan": plan.model_dump(),
        }
        if artifacts.research_result:
            diagnostics["research"] = artifacts.research_result.to_dict()
        if artifacts.web_search_result:
            diagnostics["web_search"] = artifacts.web_search_result.to_dict()
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
                research_result = await self._run_doc_retrieval_step(step, user_query)
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
        question = step.input.get("question") or user_query
        context_overrides = step.input.get("context") or {}
        step_filters = context_overrides.get("filters", default_filters)
        step_limit = context_overrides.get("limit", default_limit)

        analyst_result = await self.analyst_agent.answer_async(
            question,
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
        return self.visual_agent.run(data, title=viz_title)

    async def _run_doc_retrieval_step(self, step: PlanStep, user_query: str) -> DeepResearchResult:
        if not self.deep_research_agent:
            raise RuntimeError("DeepResearchAgent is not configured but planner requested DocRetrieval.")
        context = step.input.get("context") or {}
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
    def _coerce_research_payload(result: DeepResearchResult) -> Dict[str, Any]:
        return result.to_tabular()

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
