"""
Supervisor orchestrator that coordinates planner, analyst, research, and visual agents.
"""

import asyncio
import json
import logging
import re
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
    tool_calls: list[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReasoningDecision:
    """Outcome returned by the reasoning agent after each execution pass."""

    continue_planning: bool
    updated_context: Optional[Dict[str, Any]] = None
    rationale: Optional[str] = None


class ReasoningAgent:
    """Simple reasoning layer that decides whether additional planning is required."""

    _ENTITY_ALIAS_MAP: dict[str, tuple[str, ...]] = {
        "store": ("store", "shop", "outlet", "branch", "location"),
        "client": ("client", "customer", "account"),
        "product": ("product", "sku", "item"),
        "region": ("region", "territory", "area", "country"),
        "fund": ("fund", "portfolio", "strategy"),
        "team": ("team", "desk"),
        "sector": ("sector", "industry"),
        "channel": ("channel", "source"),
        "segment": ("segment",),
        "asset": ("asset",),
    }
    _MAX_ENTITY_RESOLUTION_ATTEMPTS = 1

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

    @staticmethod
    def _normalize_agent_name(value: Any) -> Optional[AgentName]:
        if isinstance(value, AgentName):
            return value
        if value is None:
            return None
        cleaned = str(value).strip().lower()
        if not cleaned:
            return None
        for agent in AgentName:
            if cleaned == agent.value.lower() or cleaned == agent.name.lower():
                return agent
        alias_map = {
            "analysis": AgentName.ANALYST,
            "sql": AgentName.ANALYST,
            "visualization": AgentName.VISUAL,
            "visual": AgentName.VISUAL,
            "websearch": AgentName.WEB_SEARCH,
            "web": AgentName.WEB_SEARCH,
            "docretrieval": AgentName.DOC_RETRIEVAL,
            "doc_retrieval": AgentName.DOC_RETRIEVAL,
            "research": AgentName.DOC_RETRIEVAL,
            "clarify": AgentName.CLARIFY,
        }
        return alias_map.get(cleaned)

    def _coerce_tool_rewrites(self, value: Any) -> list[dict[str, Any]]:
        if not value:
            return []
        items = value if isinstance(value, list) else [value]
        rewrites: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            agent = self._normalize_agent_name(
                item.get("agent") or item.get("tool") or item.get("target")
            )
            if not agent:
                continue
            entry: dict[str, Any] = {"agent": agent.value}
            step_id = item.get("step_id") or item.get("step") or item.get("id")
            if isinstance(step_id, str) and step_id.strip():
                entry["step_id"] = step_id.strip()
            source_step_ref = item.get("source_step_ref") or item.get("source_step")
            if isinstance(source_step_ref, str) and source_step_ref.strip():
                entry["source_step_ref"] = source_step_ref.strip()
            follow_up = item.get("follow_up") or item.get("instruction")
            if isinstance(follow_up, str) and follow_up.strip():
                entry["follow_up"] = follow_up.strip()

            question = item.get("question") or item.get("query") or item.get("rewritten_question")
            if isinstance(question, str) and question.strip():
                if agent == AgentName.WEB_SEARCH:
                    entry["query"] = question.strip()
                else:
                    entry["question"] = question.strip()

            if len(entry) > 1:
                rewrites.append(entry)
        return rewrites

    @staticmethod
    def _coerce_entity_resolution(value: Any) -> Optional[dict[str, Any]]:
        if not isinstance(value, dict):
            return None
        entity_type = str(value.get("entity_type") or "").strip()
        entity_phrase = str(value.get("entity_phrase") or value.get("entity") or "").strip()
        probe_question = str(value.get("probe_question") or "").strip()
        follow_up = str(value.get("follow_up") or "").strip()
        original_question = str(value.get("original_question") or "").strip()
        payload: dict[str, Any] = {}
        if entity_type:
            payload["entity_type"] = entity_type
        if entity_phrase:
            payload["entity_phrase"] = entity_phrase
        if probe_question:
            payload["probe_question"] = probe_question
        if follow_up:
            payload["follow_up"] = follow_up
        if original_question:
            payload["original_question"] = original_question
        return payload or None

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

        sample_values = self._sample_column_values(columns, rows)

        return {
            "row_count": len(rows),
            "columns": columns,
            "sample_values": sample_values,
            "analyst_error": analyst_error,
            "web_results_count": web_count,
            "research_findings_count": research_findings,
            "research_synthesis": research_synthesis[:240],
            "visualization_chart_type": chart_type,
        }

    @staticmethod
    def _sample_column_values(
        columns: Sequence[Any],
        rows: Sequence[Any],
        *,
        max_columns: int = 4,
        max_rows: int = 6,
        max_values: int = 4,
    ) -> Dict[str, list[str]]:
        if not columns or not rows:
            return {}
        samples: Dict[str, list[str]] = {}
        for col_index, col in enumerate(columns[:max_columns]):
            seen: list[str] = []
            for row in rows[:max_rows]:
                if not isinstance(row, (list, tuple)) or col_index >= len(row):
                    continue
                value = row[col_index]
                if value is None:
                    continue
                text = str(value).strip()
                if not text or len(text) > 80:
                    continue
                if text not in seen:
                    seen.append(text)
                if len(seen) >= max_values:
                    break
            if seen:
                samples[str(col)] = seen
        return samples

    @staticmethod
    def _structured_row_count(artifacts: PlanExecutionArtifacts) -> Optional[int]:
        if artifacts.data_payload:
            rows = artifacts.data_payload.get("rows")
            if isinstance(rows, list):
                return len(rows)
        if artifacts.analyst_result and artifacts.analyst_result.result:
            rows = artifacts.analyst_result.result.rows
            if isinstance(rows, list):
                return len(rows)
        return None

    @staticmethod
    def _pluralize_label(label: str) -> str:
        cleaned = str(label or "").strip()
        if not cleaned:
            return "items"
        lower = cleaned.lower()
        if lower.endswith("y") and len(lower) > 1:
            return f"{cleaned[:-1]}ies"
        if lower.endswith("s"):
            return cleaned
        return f"{cleaned}s"

    def _extract_entity_target(self, question: str) -> Optional[Dict[str, str]]:
        if not question:
            return None
        for entity_type, aliases in self._ENTITY_ALIAS_MAP.items():
            for alias in aliases:
                pattern = rf"\b{re.escape(alias)}s?\b\s+([A-Za-z0-9&.'\-]+(?:\s+[A-Za-z0-9&.'\-]+){{0,2}})"
                match = re.search(pattern, question, flags=re.IGNORECASE)
                if match:
                    phrase = match.group(0).strip()
                    return {
                        "entity_type": entity_type,
                        "entity_phrase": phrase,
                    }
        return None

    @staticmethod
    def _extract_entity_resolution_context(diagnostics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        extra_context = diagnostics.get("extra_context")
        if not isinstance(extra_context, dict):
            return None
        reasoning = extra_context.get("reasoning")
        if not isinstance(reasoning, dict):
            return None
        resolution = reasoning.get("entity_resolution")
        if not isinstance(resolution, dict):
            return None
        return resolution

    def _build_entity_resolution(
        self,
        *,
        user_query: str,
        diagnostics: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        target = self._extract_entity_target(user_query)
        if not target:
            return None

        existing = self._extract_entity_resolution_context(diagnostics) or {}
        attempts = int(existing.get("attempts") or 0)
        if attempts >= self._MAX_ENTITY_RESOLUTION_ATTEMPTS:
            return None

        entity_type = target["entity_type"]
        entity_phrase = target["entity_phrase"]
        plural = self._pluralize_label(entity_type)
        probe_question = f"List all {plural} names."

        return {
            "entity_type": entity_type,
            "entity_phrase": entity_phrase,
            "original_question": user_query,
            "probe_question": probe_question,
            "attempts": attempts + 1,
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
            "retry_due_to_empty, retry_due_to_low_sources, tool_rewrites, entity_resolution.",
            "tool_rewrites should be a list of objects with keys: agent, question/query,",
            "optional step_id, source_step_ref, follow_up. Use it to rewrite tool inputs.",
            "entity_resolution should be an object with keys: entity_type, entity_phrase,",
            "probe_question, follow_up, original_question. Use it when SQL results are empty",
            "and you need to resolve entity naming mismatches (e.g. Store A vs Shop A).",
            "If results are empty or errors occurred, set continue_planning=true and provide",
            "tool_rewrites or entity_resolution to improve the next tool call.",
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

        tool_rewrites = self._coerce_tool_rewrites(payload.get("tool_rewrites") or payload.get("rewrites"))
        if tool_rewrites:
            reasoning_payload["tool_rewrites"] = tool_rewrites

        entity_resolution = self._coerce_entity_resolution(payload.get("entity_resolution"))
        if entity_resolution:
            reasoning_payload["entity_resolution"] = entity_resolution

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
        row_count = self._structured_row_count(artifacts)
        analyst_error = artifacts.analyst_result and artifacts.analyst_result.error

        if (
            row_count == 0
            and has_structured_data
            and not analyst_error
            and not has_web_results
            and not has_research
            and user_query
            and plan.route in (RouteName.SIMPLE_ANALYST.value, RouteName.ANALYST_THEN_VISUAL.value)
        ):
            entity_resolution = self._build_entity_resolution(
                user_query=user_query,
                diagnostics=diagnostics,
            )
            if entity_resolution:
                rationale = "No rows returned; probing entity names to resolve mismatches."
                self.logger.debug(rationale)
                return ReasoningDecision(
                    continue_planning=True,
                    updated_context={
                        "reasoning": {
                            "previous_route": plan.route,
                            "entity_resolution": entity_resolution,
                        }
                    },
                    rationale=rationale,
                )

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
        iteration_diagnostics_history: list[Dict[str, Any]] = []
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
            plan = await asyncio.to_thread(self.planning_agent.plan, planner_request)
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
            if artifacts.clarifying_question:
                iteration_diagnostics["clarifying_question"] = artifacts.clarifying_question
            iteration_diagnostics_history.append(iteration_diagnostics)
            
            final_decision = await asyncio.to_thread(
                self.reasoning_agent.evaluate,
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
            "iterations_diagnostics": iteration_diagnostics_history,
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
            "tool_calls": combined_artifacts.tool_calls,
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
                step_start = time.perf_counter()
                tool_args: Dict[str, Any] = {"step_id": step.id, "input": step.input}
                try:
                    analyst_result, data_payload, tool_args = await self._run_analyst_step(
                        step,
                        user_query=user_query,
                        default_filters=filters,
                        default_limit=limit,
                        step_outputs=step_outputs,
                    )
                except Exception as exc:
                    duration_ms = int((time.perf_counter() - step_start) * 1000)
                    artifacts.tool_calls.append(
                        {
                            "tool_name": AgentName.ANALYST.value,
                            "arguments": tool_args,
                            "result": None,
                            "duration_ms": duration_ms,
                            "error": {"message": str(exc), "type": exc.__class__.__name__},
                        }
                    )
                    raise
                duration_ms = int((time.perf_counter() - step_start) * 1000)
                artifacts.tool_calls.append(
                    {
                        "tool_name": AgentName.ANALYST.value,
                        "arguments": tool_args,
                        "result": self._summarize_analyst_result(analyst_result, data_payload),
                        "duration_ms": duration_ms,
                        "error": self._coerce_tool_error(analyst_result.error),
                    }
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
                step_start = time.perf_counter()
                tool_args = {"step_id": step.id, "input": step.input}
                try:
                    visualization, tool_args = await self._run_visual_step(
                        step,
                        user_query=user_query,
                        title=title,
                        fallback_payload=artifacts.data_payload,
                        step_outputs=step_outputs,
                    )
                except Exception as exc:
                    duration_ms = int((time.perf_counter() - step_start) * 1000)
                    artifacts.tool_calls.append(
                        {
                            "tool_name": AgentName.VISUAL.value,
                            "arguments": tool_args,
                            "result": None,
                            "duration_ms": duration_ms,
                            "error": {"message": str(exc), "type": exc.__class__.__name__},
                        }
                    )
                    raise
                duration_ms = int((time.perf_counter() - step_start) * 1000)
                artifacts.tool_calls.append(
                    {
                        "tool_name": AgentName.VISUAL.value,
                        "arguments": tool_args,
                        "result": visualization,
                        "duration_ms": duration_ms,
                        "error": None,
                    }
                )
                artifacts.visualization = visualization
                step_outputs[step.id] = {
                    "agent": AgentName.VISUAL.value,
                    "visualization": visualization,
                }
                continue

            if agent_name == AgentName.DOC_RETRIEVAL.value:
                step_start = time.perf_counter()
                tool_args = {"step_id": step.id, "input": step.input}
                try:
                    research_result, tool_args = await self._run_doc_retrieval_step(
                        step, user_query, step_outputs
                    )
                except Exception as exc:
                    duration_ms = int((time.perf_counter() - step_start) * 1000)
                    artifacts.tool_calls.append(
                        {
                            "tool_name": AgentName.DOC_RETRIEVAL.value,
                            "arguments": tool_args,
                            "result": None,
                            "duration_ms": duration_ms,
                            "error": {"message": str(exc), "type": exc.__class__.__name__},
                        }
                    )
                    raise
                duration_ms = int((time.perf_counter() - step_start) * 1000)
                artifacts.tool_calls.append(
                    {
                        "tool_name": AgentName.DOC_RETRIEVAL.value,
                        "arguments": tool_args,
                        "result": research_result.to_dict() if research_result else None,
                        "duration_ms": duration_ms,
                        "error": None,
                    }
                )
                artifacts.research_result = research_result
                step_outputs[step.id] = {
                    "agent": AgentName.DOC_RETRIEVAL.value,
                    "research_result": research_result,
                }
                if not artifacts.data_payload:
                    artifacts.data_payload = research_result.to_tabular()
                continue

            if agent_name == AgentName.WEB_SEARCH.value:
                step_start = time.perf_counter()
                tool_args = {"step_id": step.id, "input": step.input}
                try:
                    web_search_result, tool_args = await self._run_web_search_step(step, user_query)
                except Exception as exc:
                    duration_ms = int((time.perf_counter() - step_start) * 1000)
                    artifacts.tool_calls.append(
                        {
                            "tool_name": AgentName.WEB_SEARCH.value,
                            "arguments": tool_args,
                            "result": None,
                            "duration_ms": duration_ms,
                            "error": {"message": str(exc), "type": exc.__class__.__name__},
                        }
                    )
                    raise
                duration_ms = int((time.perf_counter() - step_start) * 1000)
                artifacts.tool_calls.append(
                    {
                        "tool_name": AgentName.WEB_SEARCH.value,
                        "arguments": tool_args,
                        "result": web_search_result.to_dict() if web_search_result else None,
                        "duration_ms": duration_ms,
                        "error": None,
                    }
                )
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
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> tuple[AnalystQueryResponse, Dict[str, Any], Dict[str, Any]]:
        if not self.analyst_agent:
            raise RuntimeError("AnalystAgent is not configured but planner requested SQL analysis.")
        base_question = step.input.get("question") or user_query
        question = base_question
        context_overrides = step.input.get("context") or {}
        step_filters = context_overrides.get("filters", default_filters)
        step_limit = context_overrides.get("limit", default_limit)
        conversation_context = context_overrides.get("conversation_context")
        source_step_ref = step.input.get("source_step_ref")
        tool_context = self._build_step_context_summary(source_step_ref, step_outputs)
        if tool_context:
            conversation_context = self._merge_conversation_context(conversation_context, tool_context)

        if tool_context:
            rewritten = await asyncio.to_thread(
                self._rewrite_question_with_llm,
                question=question,
                tool_context=tool_context,
                original_question=step.input.get("original_question") or user_query,
            )
            if rewritten:
                question = rewritten

        follow_up = step.input.get("follow_up")
        if isinstance(follow_up, str) and follow_up.strip():
            if follow_up.strip().lower() not in question.lower():
                question = f"{question}\nFollow-up: {follow_up.strip()}"

        analyst_result: AnalystQueryResponse = await self.analyst_agent.answer_async(
            question,
            conversation_context=conversation_context,
            filters=step_filters,
            limit=step_limit,
        )
        data_payload = self._extract_data_payload(analyst_result)
        tool_args: Dict[str, Any] = {
            "step_id": step.id,
            "input": step.input,
            "question": question,
            "filters": step_filters,
            "limit": step_limit,
        }
        if base_question and base_question != question:
            tool_args["original_question"] = base_question
        if conversation_context:
            tool_args["conversation_context"] = conversation_context
        if source_step_ref:
            tool_args["source_step_ref"] = source_step_ref
        return analyst_result, data_payload, tool_args

    async def _run_visual_step(
        self,
        step: PlanStep,
        *,
        user_query: str,
        title: Optional[str],
        fallback_payload: Dict[str, Any],
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        reference_id = step.input.get("rows_ref")
        referenced_payload = self._resolve_rows_reference(reference_id, step_outputs)
        data = referenced_payload or fallback_payload or {"columns": [], "rows": []}
        viz_title = title or f"Visualization for '{user_query}'"
        user_intent = step.input.get("user_intent")
        visualization = await asyncio.to_thread(
            self.visual_agent.run,
            data,
            title=viz_title,
            question=user_query,
            user_intent=user_intent,
        )
        tool_args: Dict[str, Any] = {
            "step_id": step.id,
            "input": step.input,
            "question": user_query,
            "title": viz_title,
            "data_summary": self._summarize_tabular_payload(data),
        }
        if reference_id:
            tool_args["rows_ref"] = reference_id
        if user_intent:
            tool_args["user_intent"] = user_intent
        return visualization, tool_args

    async def _run_doc_retrieval_step(
        self,
        step: PlanStep,
        user_query: str,
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> tuple[DeepResearchResult, Dict[str, Any]]:
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
        result = await self.deep_research_agent.research_async(
            question=question,
            context=context,
            timebox_seconds=timebox,
        )
        tool_args: Dict[str, Any] = {
            "step_id": step.id,
            "input": step.input,
            "question": question,
            "context": context,
            "timebox_seconds": timebox,
        }
        if source_step_ref:
            tool_args["source_step_ref"] = source_step_ref
        return result, tool_args

    async def _run_web_search_step(
        self,
        step: PlanStep,
        user_query: str,
    ) -> tuple[WebSearchResult, Dict[str, Any]]:
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

        result = await self.web_search_agent.search_async(
            query,
            max_results=max_results_value,
            region=region,
            safe_search=safe_search,
            timebox_seconds=timebox,
        )
        tool_args: Dict[str, Any] = {
            "step_id": step.id,
            "input": step.input,
            "query": query,
            "max_results": max_results_value,
            "region": region,
            "safe_search": safe_search,
            "timebox_seconds": timebox,
        }
        return result, tool_args

    @staticmethod
    def _coerce_tool_error(error: Any) -> Optional[Dict[str, Any]]:
        if not error:
            return None
        if isinstance(error, dict):
            return error
        return {"message": str(error)}

    @staticmethod
    def _summarize_tabular_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        columns = payload.get("columns")
        if isinstance(columns, list):
            summary["columns"] = columns
        rows = payload.get("rows")
        if isinstance(rows, list):
            summary["row_count"] = len(rows)
        return summary

    def _summarize_analyst_result(
        self,
        analyst_result: AnalystQueryResponse,
        data_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "sql_canonical": analyst_result.sql_canonical,
            "sql_executable": analyst_result.sql_executable,
            "dialect": analyst_result.dialect,
            "model_name": analyst_result.model_name,
            "execution_time_ms": analyst_result.execution_time_ms,
        }
        query_result = analyst_result.result
        if query_result:
            row_count = query_result.rowcount
            if row_count is None and isinstance(query_result.rows, list):
                row_count = len(query_result.rows)
            if row_count is not None:
                summary["row_count"] = row_count
            if query_result.elapsed_ms is not None:
                summary["elapsed_ms"] = query_result.elapsed_ms
            if query_result.columns:
                summary["columns"] = list(query_result.columns)
            if query_result.source_sql:
                summary["source_sql"] = query_result.source_sql
        elif data_payload:
            summary.update(self._summarize_tabular_payload(data_payload))
        return summary

    @staticmethod
    def _extract_data_payload(analyst_result: AnalystQueryResponse) -> Dict[str, Any]:
        if analyst_result.result:
            return {
                "columns": analyst_result.result.columns,
                "rows": analyst_result.result.rows,
            }
        return {}

    @staticmethod
    def _trim_text(value: str, limit: int = 280) -> str:
        cleaned = str(value or "").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit].rstrip() + "..."

    @staticmethod
    def _merge_conversation_context(base: Optional[str], extra: str) -> str:
        base_text = str(base or "").strip()
        extra_text = str(extra or "").strip()
        if not extra_text:
            return base_text
        if base_text:
            return f"{base_text}\n\n{extra_text}"
        return extra_text

    def _build_step_context_summary(
        self,
        reference_id: Optional[str],
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> Optional[str]:
        if not reference_id:
            return None
        referenced = step_outputs.get(reference_id)
        if not referenced:
            return None

        parts: list[str] = []
        research_result = referenced.get("research_result")
        if isinstance(research_result, DeepResearchResult):
            if research_result.synthesis:
                parts.append(
                    f"Research synthesis: {self._trim_text(research_result.synthesis, 360)}"
                )
            if research_result.findings:
                insights = "; ".join(
                    self._trim_text(finding.insight, 160) for finding in research_result.findings[:3]
                )
                parts.append(f"Research findings: {insights}")

        web_search_result = referenced.get("web_search_result")
        if isinstance(web_search_result, WebSearchResult) and web_search_result.results:
            sources = "; ".join(
                f"{self._trim_text(item.title, 100)} ({item.url})"
                for item in web_search_result.results[:3]
            )
            parts.append(f"Web sources: {sources}")

        data_payload = referenced.get("data_payload")
        if isinstance(data_payload, dict):
            columns = data_payload.get("columns")
            rows = data_payload.get("rows")
            if isinstance(columns, list) and columns:
                column_list = ", ".join(str(col) for col in columns[:8])
                parts.append(f"Data columns: {self._trim_text(column_list, 180)}")
            if isinstance(rows, list):
                parts.append(f"Row count: {len(rows)}")
                if isinstance(columns, list):
                    samples = self._extract_sample_values(columns, rows)
                    if samples:
                        parts.extend(samples)

        if not parts:
            return None
        return "\n".join(parts)

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

    @classmethod
    def _parse_llm_payload(cls, response: str) -> Optional[Dict[str, Any]]:
        blob = cls._extract_json_blob(response)
        if not blob:
            return None
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _rewrite_question_with_llm(
        self,
        *,
        question: str,
        tool_context: str,
        original_question: str,
    ) -> Optional[str]:
        llm = self.reasoning_agent.llm if self.reasoning_agent else None
        if not llm:
            return None

        prompt_sections = [
            "You rewrite analyst questions to align with known entity names.",
            "Return ONLY JSON with key: rewritten_question.",
            f"Original question: {original_question}",
            f"Current question: {question}",
            f"Tool context: {tool_context}",
        ]
        prompt = "\n".join(prompt_sections)
        try:
            response = llm.complete(prompt, temperature=0.0, max_tokens=160)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("LLM question rewrite failed: %s", exc)
            return None

        payload = self._parse_llm_payload(str(response))
        if not payload:
            return None
        rewritten = payload.get("rewritten_question") or payload.get("question")
        if not isinstance(rewritten, str):
            return None
        rewritten = rewritten.strip()
        if not rewritten:
            return None
        return rewritten

    @staticmethod
    def _extract_sample_values(columns: Sequence[Any], rows: Sequence[Any]) -> list[str]:
        if not rows or not columns:
            return []
        sample_lines: list[str] = []
        max_columns = 4
        max_rows = 6
        max_values = 4

        for col_index, col in enumerate(columns[:max_columns]):
            seen: list[str] = []
            for row in rows[:max_rows]:
                if not isinstance(row, (list, tuple)) or col_index >= len(row):
                    continue
                value = row[col_index]
                if value is None:
                    continue
                text = str(value).strip()
                if not text or len(text) > 80:
                    continue
                if text not in seen:
                    seen.append(text)
                if len(seen) >= max_values:
                    break
            if seen:
                sample_values = ", ".join(seen)
                sample_lines.append(f"Sample values for {col}: {sample_values}")

        return sample_lines

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
        if updates.tool_calls:
            base.tool_calls.extend(updates.tool_calls)

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
