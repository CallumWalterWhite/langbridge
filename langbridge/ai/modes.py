"""Shared mode contracts for Langbridge AI."""

from __future__ import annotations

from enum import Enum
from typing import Any

from langbridge.ai.base import AgentIOContract


class AnalystAgentMode(str, Enum):
    auto = "auto"
    sql = "sql"
    context_analysis = "context_analysis"
    research = "research"


_ANALYST_MODE_ALIASES = {
    "answer": AnalystAgentMode.context_analysis.value,
    "analysis": AnalystAgentMode.context_analysis.value,
    "context": AnalystAgentMode.context_analysis.value,
    "deep_research": AnalystAgentMode.research.value,
    "deep-research": AnalystAgentMode.research.value,
    "web_research": AnalystAgentMode.research.value,
    "web-research": AnalystAgentMode.research.value,
}

_ANALYST_OUTPUT_OPTIONAL_KEYS = [
    "analysis_path",
    "sql_canonical",
    "sql_executable",
    "selected_datasets",
    "selected_semantic_models",
    "query_scope",
    "outcome",
    "error_taxonomy",
    "evidence",
    "synthesis",
    "findings",
    "sources",
    "follow_ups",
    "review_hints",
]


def normalize_analyst_mode(
    value: Any,
    *,
    default: AnalystAgentMode | None = None,
) -> AnalystAgentMode | None:
    text = str(value or "").strip().lower()
    if not text:
        return default
    normalized = _ANALYST_MODE_ALIASES.get(text, text)
    try:
        return AnalystAgentMode(normalized)
    except ValueError as exc:
        raise ValueError(f"Unsupported analyst mode '{text}'.") from exc


def normalize_analyst_task_input(
    input_payload: dict[str, Any] | None,
    *,
    requested_mode: Any = None,
) -> dict[str, Any]:
    normalized = dict(input_payload or {})
    raw_mode = normalized.get("agent_mode")
    if raw_mode in (None, ""):
        raw_mode = normalized.get("mode")
    if raw_mode in (None, ""):
        raw_mode = requested_mode
    mode = normalize_analyst_mode(raw_mode, default=AnalystAgentMode.auto)
    normalized.pop("mode", None)
    if mode is None or mode == AnalystAgentMode.auto:
        normalized.pop("agent_mode", None)
        return normalized
    normalized["agent_mode"] = mode.value
    return normalized


def analyst_output_contract_for_task_input(
    input_payload: dict[str, Any] | None,
    *,
    requested_mode: Any = None,
) -> AgentIOContract:
    normalized = normalize_analyst_task_input(input_payload, requested_mode=requested_mode)
    mode = normalize_analyst_mode(normalized.get("agent_mode"), default=AnalystAgentMode.auto)
    if mode == AnalystAgentMode.research:
        return AgentIOContract(
            required_keys=["analysis", "result", "synthesis", "sources", "findings"],
            optional_keys=list(_ANALYST_OUTPUT_OPTIONAL_KEYS),
        )
    if mode == AnalystAgentMode.sql:
        return AgentIOContract(
            required_keys=["analysis", "result", "outcome", "evidence", "review_hints"],
            optional_keys=list(_ANALYST_OUTPUT_OPTIONAL_KEYS),
        )
    if mode == AnalystAgentMode.context_analysis:
        return AgentIOContract(
            required_keys=["analysis", "result", "evidence", "review_hints"],
            optional_keys=list(_ANALYST_OUTPUT_OPTIONAL_KEYS),
        )
    return AgentIOContract(
        required_keys=["analysis", "result", "evidence", "review_hints"],
        optional_keys=list(_ANALYST_OUTPUT_OPTIONAL_KEYS),
    )


__all__ = [
    "AnalystAgentMode",
    "analyst_output_contract_for_task_input",
    "normalize_analyst_mode",
    "normalize_analyst_task_input",
]
