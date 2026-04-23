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
    analysis_payload: dict[str, Any] | None,
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
        "- Put the main user-facing substance in answer.\n"
        "- Prefer the verified analytical payload as the answer backbone when it is available.\n"
        "- Preserve material metrics, findings, caveats, and evidence from Analysis and Research instead of flattening them.\n"
        "- Decide the answer depth from the question and evidence, not from a fixed template.\n"
        "- Explain errors and blockers clearly without inventing recovery success.\n"
        "- Use a detailed answer when the user asks for explanation, evidence, comparisons, drivers, caveats, or source-backed reasoning.\n"
        "- Use a concise answer only when the question is straightforward and the evidence is simple.\n"
        "- When detailed explanation is needed, include the concrete values, findings, caveats, and evidence-backed reasoning needed to fully answer the question.\n"
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
        f"Analysis: {json.dumps(analysis_payload or {}, default=str)}\n"
        f"Research: {json.dumps(research_payload or {}, default=str)}\n"
        f"Answer: {json.dumps(answer_payload or {}, default=str)}\n"
        f"Visualization: {json.dumps(visualization.model_dump(mode='json') if visualization else None, default=str)}\n"
    )


__all__ = ["build_presentation_prompt"]
