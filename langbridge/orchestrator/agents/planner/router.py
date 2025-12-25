
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .models import (
    AgentName,
    PlanStep,
    PlannerRequest,
    PlanningConstraints,
    RouteDecision,
    RouteName,
    RouteSignals,
)


_SQL_KEYWORDS: Tuple[str, ...] = (
    "show me",
    "list",
    "count",
    "top",
    "bottom",
    "average",
    "avg",
    "sum",
    "trend",
    "growth",
    "breakdown",
    "filter",
    "where",
    "group by",
    "over time",
    "compare",
)

_VISUAL_KEYWORDS: Tuple[str, ...] = (
    "chart",
    "graph",
    "plot",
    "visual",
    "visualise",
    "visualize",
    "bar",
    "line",
    "dashboard",
    "heatmap",
    "scatter",
    "timeline",
)

_RESEARCH_KEYWORDS: Tuple[str, ...] = (
    "summarize",
    "summarise",
    "synthesis",
    "whitepaper",
    "pdf",
    "doc",
    "document",
    "report",
    "outlook",
    "insight",
    "industry",
    "explain why",
    "root cause",
    "policy",
    "memo",
    "news",
    "compare reports",
    "research",
)

_WEB_SEARCH_KEYWORDS: Tuple[str, ...] = (
    "web",
    "search the web",
    "web search",
    "internet",
    "online",
    "google",
    "bing",
    "duckduckgo",
    "news",
    "headline",
    "article",
    "press release",
    "site:",
    "wikipedia",
)

_ENTITY_HINTS: Tuple[str, ...] = (
    "fund",
    "portfolio",
    "account",
    "region",
    "country",
    "client",
    "customer",
    "product",
    "team",
    "sector",
    "strategy",
    "channel",
    "segment",
    "asset",
)

_TIME_HINTS: Tuple[str, ...] = (
    "yesterday",
    "today",
    "last",
    "previous",
    "current",
    "this",
    "quarter",
    "month",
    "year",
    "week",
    "day",
    "daily",
    "monthly",
    "ytd",
    "mtd",
    "q1",
    "q2",
    "q3",
    "q4",
    "fy",
    "202",
    "20",
    "2020",
    "2021",
    "2022",
    "2023",
    "2024",
    "2025",
)

_AGGREGATION_HINTS: Tuple[str, ...] = (
    "top",
    "bottom",
    "rank",
    "compare",
    "by",
    "versus",
    "vs",
    "per",
    "distribution",
    "histogram",
    "trend",
    "over time",
    "breakdown",
)

_AMBIGUITY_PHRASES: Tuple[str, ...] = (
    "show me performance",
    "show performance",
    "how are things going",
    "tell me the performance",
    "give me performance",
    "show me results",
    "update me",
)

_NUMBER_PATTERN = re.compile(r"\b\d{4}\b")


def _contains_keyword(text: str, keywords: Iterable[str]) -> bool:
    for keyword in keywords:
        if " " in keyword:
            if keyword in text:
                return True
        else:
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, text):
                return True
    return False


def _extract_signals(question: str) -> RouteSignals:
    lowered = question.lower()
    tokens = lowered.split()
    has_sql_signals = _contains_keyword(lowered, _SQL_KEYWORDS) or bool(
        re.search(r"\b(select|sql|table|column)\b", lowered)
    )
    has_visual_cues = _contains_keyword(lowered, _VISUAL_KEYWORDS)
    has_research_signals = _contains_keyword(lowered, _RESEARCH_KEYWORDS)
    has_web_search_signals = _contains_keyword(lowered, _WEB_SEARCH_KEYWORDS)
    has_entity_reference = _contains_keyword(lowered, _ENTITY_HINTS)
    has_time_reference = _contains_keyword(lowered, _TIME_HINTS) or bool(_NUMBER_PATTERN.search(lowered))
    chartable = has_visual_cues or (
        has_sql_signals and _contains_keyword(lowered, _AGGREGATION_HINTS)
    )

    requires_clarification = False
    if _contains_keyword(lowered, _AMBIGUITY_PHRASES):
        requires_clarification = True
    elif len(tokens) <= 4 and not has_research_signals and not has_web_search_signals and "?" not in lowered:
        requires_clarification = True
    elif "performance" in lowered and not has_entity_reference and not has_research_signals and not has_web_search_signals:
        requires_clarification = True

    return RouteSignals(
        has_sql_signals=has_sql_signals,
        has_visual_cues=has_visual_cues,
        has_research_signals=has_research_signals,
        has_web_search_signals=has_web_search_signals,
        requires_clarification=requires_clarification,
        chartable=chartable,
        has_time_reference=has_time_reference,
        has_entity_reference=has_entity_reference,
    )


def _estimate_step_count(route: RouteName, signals: RouteSignals, constraints: PlanningConstraints) -> int:
    if route == RouteName.SIMPLE_ANALYST:
        return 1
    if route == RouteName.ANALYST_THEN_VISUAL:
        return 2
    if route == RouteName.WEB_SEARCH:
        return 1
    if route == RouteName.DEEP_RESEARCH:
        steps = 1  # Doc retrieval mandatory
        if signals.has_sql_signals:
            steps += 1
        if signals.chartable and constraints.require_viz_when_chartable and signals.has_sql_signals:
            steps += 1
        return steps
    return 1


def _score_simple_analyst(signals: RouteSignals) -> float:
    score = 0.0
    if signals.has_sql_signals:
        score += 3.0
    if signals.has_entity_reference:
        score += 1.0
    if signals.has_time_reference:
        score += 1.0
    if signals.chartable:
        score += 0.5
    if signals.has_research_signals:
        score -= 1.5
    return score


def _score_analyst_then_visual(signals: RouteSignals) -> float:
    score = _score_simple_analyst(signals)
    if signals.chartable:
        score += 2.0
    if signals.has_visual_cues:
        score += 1.5
    return score


def _score_web_search(signals: RouteSignals, constraints: PlanningConstraints) -> float:
    if not signals.has_web_search_signals:
        return float("-inf")
    score = 3.0
    if signals.has_research_signals:
        score += 1.0
    if signals.has_sql_signals:
        score -= 2.0
    if constraints.prefer_low_latency:
        score += 0.5
    return score


def _score_deep_research(signals: RouteSignals, constraints: PlanningConstraints) -> float:
    score = 0.0
    if signals.has_research_signals:
        score += 3.5
    if not signals.has_sql_signals:
        score += 1.0
    if signals.has_sql_signals:
        score += 0.5  # favour hybrid plans for mixed intents
    if constraints.prefer_low_latency:
        score -= 2.0
    if constraints.cost_sensitivity == "high":
        score -= 1.0
    elif constraints.cost_sensitivity == "low":
        score += 0.5
    return score


def _select_best_route(route_scores: Dict[RouteName, float]) -> RouteName:
    priority = (
        RouteName.SIMPLE_ANALYST,
        RouteName.ANALYST_THEN_VISUAL,
        RouteName.WEB_SEARCH,
        RouteName.DEEP_RESEARCH,
    )
    best_route = RouteName.SIMPLE_ANALYST
    best_score = float("-inf")
    for route in priority:
        score = route_scores.get(route, float("-inf"))
        if score > best_score:
            best_score = score
            best_route = route
    return best_route


def _build_justification(route: RouteName, signals: RouteSignals) -> str:
    if route == RouteName.SIMPLE_ANALYST:
        parts = ["SQL-friendly intent detected"]
        if signals.has_entity_reference:
            parts.append("entity cues present")
        if signals.has_time_reference:
            parts.append("time window specified")
        if signals.chartable and not signals.has_visual_cues:
            parts.append("charting optional; prioritising low latency")
        return "; ".join(parts) + "."
    if route == RouteName.ANALYST_THEN_VISUAL:
        parts = ["SQL intent with visualization cues"]
        if signals.chartable:
            parts.append("aggregations suitable for charting")
        return "; ".join(parts) + "."
    if route == RouteName.WEB_SEARCH:
        parts = ["Explicit web lookup requested"]
        if signals.has_research_signals:
            parts.append("news or external sources referenced")
        return "; ".join(parts) + "."
    if route == RouteName.DEEP_RESEARCH:
        parts = ["Unstructured research signals dominate"]
        if signals.has_sql_signals:
            parts.append("will validate with analytics as a follow-up")
        return "; ".join(parts) + "."
    return "Question requires clarification before proceeding."


def choose_route(request: PlannerRequest) -> RouteDecision:
    constraints = request.constraints
    signals = _extract_signals(request.question)

    if signals.requires_clarification:
        justification = "Ambiguous intent detected; clarification is required before safe execution."
        assumptions: list[str] = []
        if not signals.has_entity_reference:
            assumptions.append("Need specific entity or scope before querying data sources.")
        if not signals.has_time_reference:
            assumptions.append("Need time window to avoid misaligned metrics.")
        return RouteDecision(
            route=RouteName.CLARIFY,
            justification=justification,
            signals=signals,
            assumptions=assumptions,
        )

    # Hard routing rules
    if constraints.require_viz_when_chartable and signals.chartable and constraints.max_steps >= 2:
        justification = _build_justification(RouteName.ANALYST_THEN_VISUAL, signals)
        return RouteDecision(
            route=RouteName.ANALYST_THEN_VISUAL,
            justification=justification,
            signals=signals,
        )

    route_scores: Dict[RouteName, float] = {}

    # Simple analyst route is always available as long as at least one step permitted.
    if constraints.max_steps >= _estimate_step_count(RouteName.SIMPLE_ANALYST, signals, constraints):
        route_scores[RouteName.SIMPLE_ANALYST] = _score_simple_analyst(signals)
    else:
        route_scores[RouteName.SIMPLE_ANALYST] = float("-inf")

    if constraints.max_steps >= _estimate_step_count(RouteName.ANALYST_THEN_VISUAL, signals, constraints):
        route_scores[RouteName.ANALYST_THEN_VISUAL] = _score_analyst_then_visual(signals)
    else:
        route_scores[RouteName.ANALYST_THEN_VISUAL] = float("-inf")

    if constraints.allow_web_search:
        estimated_steps = _estimate_step_count(RouteName.WEB_SEARCH, signals, constraints)
        if constraints.max_steps >= estimated_steps:
            route_scores[RouteName.WEB_SEARCH] = _score_web_search(signals, constraints)
        else:
            route_scores[RouteName.WEB_SEARCH] = float("-inf")
    else:
        route_scores[RouteName.WEB_SEARCH] = float("-inf")

    if constraints.allow_deep_research:
        estimated_steps = _estimate_step_count(RouteName.DEEP_RESEARCH, signals, constraints)
        if constraints.max_steps >= estimated_steps:
            route_scores[RouteName.DEEP_RESEARCH] = _score_deep_research(signals, constraints)
        else:
            route_scores[RouteName.DEEP_RESEARCH] = float("-inf")
    else:
        route_scores[RouteName.DEEP_RESEARCH] = float("-inf")

    selected_route = _select_best_route(route_scores)
    justification = _build_justification(selected_route, signals)

    assumptions: list[str] = []
    if selected_route == RouteName.ANALYST_THEN_VISUAL and constraints.max_steps < 2:
        assumptions.append("Visualization step may be skipped if latency constraints tighten further.")
    if (
        selected_route == RouteName.DEEP_RESEARCH
        and constraints.timebox_seconds
        and constraints.timebox_seconds < 30
    ):
        assumptions.append("Document retrieval scoped to high-signal sources due to tight timebox.")

    return RouteDecision(
        route=selected_route,
        justification=justification,
        signals=signals,
        assumptions=assumptions,
    )


def _infer_visual_intent(question: str) -> str:
    lowered = question.lower()
    if "trend" in lowered or "over time" in lowered:
        return "time_series_comparison"
    if "versus" in lowered or "vs " in lowered:
        return "comparative_view"
    if "distribution" in lowered or "histogram" in lowered:
        return "distribution_analysis"
    if "top" in lowered or "rank" in lowered:
        return "ranked_highlights"
    return "insight_visualization"


def _build_clarifying_question(signals: RouteSignals, question: str) -> str:
    missing = []
    if not signals.has_entity_reference:
        missing.append("which entity or segment you want analysed")
    if not signals.has_time_reference:
        missing.append("the time period to evaluate")
    if missing:
        return (
            "To move forward, please specify "
            + " and ".join(missing)
            + ", for example 'fund performance by region for 2024 Q1'."
        )
    return (
        "Could you provide a bit more detail so I can plan safely? "
        "Let me know the exact metric and time window you care about."
    )


def build_steps(decision: RouteDecision, request: PlannerRequest) -> List[PlanStep]:
    constraints = request.constraints
    steps: List[PlanStep] = []
    step_counter = 1

    def _append_step(agent: AgentName, input_payload: dict, expected_output: dict) -> None:
        nonlocal step_counter
        if len(steps) >= constraints.max_steps:
            return
        steps.append(
            PlanStep(
                id=f"step-{step_counter}",
                agent=agent.value,
                input=input_payload,
                expected_output=expected_output,
            )
        )
        step_counter += 1

    if decision.route == RouteName.CLARIFY:
        _append_step(
            AgentName.CLARIFY,
            {
                "clarifying_question": _build_clarifying_question(decision.signals, request.question),
                "original_question": request.question,
            },
            {"awaiting_user": True},
        )
        return steps

    base_input = {
        "question": request.question,
        "context": request.context or {},
        "constraints": request.constraints.model_dump(),
    }

    if decision.route == RouteName.SIMPLE_ANALYST:
        _append_step(
            AgentName.ANALYST,
            base_input,
            {
                "rows": "tabular_result_set",
                "schema": "column_metadata",
                "final_sql": "string",
            },
        )
        return steps

    if decision.route == RouteName.ANALYST_THEN_VISUAL:
        _append_step(
            AgentName.ANALYST,
            base_input,
            {
                "rows": "tabular_result_set",
                "schema": "column_metadata",
                "final_sql": "string",
            },
        )
        if len(steps) < constraints.max_steps:
            _append_step(
                AgentName.VISUAL,
                {
                    "rows_ref": steps[0].id,
                    "schema_ref": steps[0].id,
                    "user_intent": _infer_visual_intent(request.question),
                },
                {
                    "viz_spec": "json_visualization_spec",
                    "insight_summary": "string",
                },
            )
        return steps

    if decision.route == RouteName.WEB_SEARCH:
        context = request.context or {}
        _append_step(
            AgentName.WEB_SEARCH,
            {
                "query": request.question,
                "context": context,
                "max_results": context.get("max_results", 6),
                "region": context.get("region"),
                "safe_search": context.get("safe_search"),
                "timebox_seconds": constraints.timebox_seconds,
            },
            {
                "results": "web_search_results",
                "sources": "list_of_urls",
            },
        )
        return steps

    if decision.route == RouteName.DEEP_RESEARCH:
        _append_step(
            AgentName.DOC_RETRIEVAL,
            {
                "question": request.question,
                "context": request.context or {},
                "timebox_seconds": constraints.timebox_seconds,
            },
            {
                "synthesis": "key_findings_with_citations",
                "evidence": "source_references",
            },
        )
        doc_step_id = steps[0].id if steps else None
        if (
            decision.signals.has_sql_signals
            and len(steps) < constraints.max_steps
        ):
            _append_step(
                AgentName.ANALYST,
                {
                    **base_input,
                    "follow_up": "Validate top qualitative claims from document synthesis.",
                    "source_step_ref": doc_step_id,
                },
                {
                    "rows": "tabular_verification_results",
                    "schema": "column_metadata",
                    "final_sql": "string",
                },
            )
        if (
            decision.signals.chartable
            and constraints.require_viz_when_chartable
            and len(steps) < constraints.max_steps
            and any(step.agent == AgentName.ANALYST.value for step in steps)
        ):
            last_analyst_step = next(
                (step.id for step in reversed(steps) if step.agent == AgentName.ANALYST.value),
                doc_step_id,
            )
            _append_step(
                AgentName.VISUAL,
                {
                    "rows_ref": last_analyst_step,
                    "schema_ref": last_analyst_step,
                    "user_intent": _infer_visual_intent(request.question),
                },
                {
                    "viz_spec": "json_visualization_spec",
                    "insight_summary": "string",
                },
            )
        return steps

    raise ValueError(f"Unsupported route {decision.route}.")


__all__ = ["choose_route", "build_steps"]
