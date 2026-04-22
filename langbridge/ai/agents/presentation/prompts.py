"""Prompt builders for the Langbridge presentation agent."""
import json
from typing import Any

from langbridge.ai.tools.charting import ChartSpec


def build_presentation_prompt(
    *,
    question: str,
    mode: str,
    context: dict[str, Any],
    data_payload: dict[str, Any] | None,
    research_payload: dict[str, Any] | None,
    answer_payload: dict[str, Any] | None,
    visualization: ChartSpec | None,
) -> str:
    return (
        "Compose the final Langbridge response.\n"
        "Return STRICT JSON only with keys: summary, result, visualization, research, answer, diagnostics.\n"
        "Rules:\n"
        "- Do not invent facts beyond provided step outputs and context.\n"
        "- Keep summary concise and user-facing.\n"
        "- For clarification mode, put the exact clarification question in answer.\n"
        "- For failure mode, explain the concrete blocker or error without inventing recovery success.\n"
        "- Preserve provided result data when present.\n"
        "- Include visualization only when supported by provided visualization context.\n"
        "- Keep diagnostics as a compact object.\n\n"
        f"Mode: {mode}\n"
        f"Question: {question}\n"
        f"Context error: {context.get('error') or ''}\n"
        f"Clarification: {context.get('clarification_question') or ''}\n"
        f"Conversation memory: {context.get('memory_context') or ''}\n"
        f"Data: {json.dumps(data_payload or {}, default=str)}\n"
        f"Research: {json.dumps(research_payload or {}, default=str)}\n"
        f"Answer: {json.dumps(answer_payload or {}, default=str)}\n"
        f"Visualization: {json.dumps(visualization.model_dump(mode='json') if visualization else None, default=str)}\n"
    )


__all__ = ["build_presentation_prompt"]
