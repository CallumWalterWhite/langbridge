"""Prompt builders for the Langbridge AI meta-controller."""
import json


def build_meta_controller_route_prompt(
    *,
    question: str,
    context: dict[str, object],
    force_plan: bool,
    requested_agent_mode: str | None,
    specification_payloads: list[dict[str, object]],
) -> str:
    return (
        "Decide Langbridge agent route.\n"
        "You are the runtime gateway. Route from agent specifications, not keyword scores.\n"
        "Return STRICT JSON only:\n"
        "{"
        "\"action\":\"direct|plan|clarify|abort\","
        "\"rationale\":\"short reason\","
        "\"agent_name\":\"exact agent name or null\","
        "\"task_kind\":\"supported task kind or null\","
        "\"input\":{},"
        "\"clarification_question\":\"question or null\","
        "\"plan_guidance\":\"guidance for planner or null\""
        "}\n"
        "Decision rules:\n"
        "- direct: choose when one available agent can answer safely within its scope, tools, output contract and doesn't require multi-step recovery. Used when one specialist can complete the request cleanly. Used on MCP requests.\n"
        "- plan: choose when the request needs staged execution, evidence gathering, recovery, or verification-aware work. Also required when the request requires multi-source review or visuals.\n"
        "- clarify: choose when a blocking detail is missing, such as metric, dataset, entity, time period, comparison frame, or source scope.\n"
        "- abort: choose only when the request is unsupported, unsafe, or impossible with available agents.\n"
        "- Prefer clarify over guesswork when missing detail would materially change the answer.\n"
        "- Prefer direct over plan when one specialist can complete the request cleanly.\n"
        "- agent_name must exactly match one available agent when action is direct.\n"
        "- task_kind must be one of the selected agent's supported task kinds when action is direct.\n"
        "- If you choose a direct analyst route, input.agent_mode may only be auto, sql, context_analysis, or research.\n"
        "- Never emit answer, analysis, deep_research, mode, or any other alias. Use input.agent_mode only.\n"
        "- If requested_agent_mode is set, preserve it for direct analyst routes unless clarification is required.\n"
        "- If force_plan is true, do not choose direct.\n"
        "- Keep rationale short and concrete.\n\n"
        f"Force plan: {force_plan}\n"
        f"Requested agent mode: {requested_agent_mode or ''}\n"
        f"Question: {question}\n"
        f"Conversation context:\n{context.get('conversation_context') or ''}\n"
        f"Memory context:\n{context.get('memory_context') or ''}\n"
        f"Runtime context keys: {json.dumps(sorted(context.keys()))}\n"
        f"Available agent specifications:\n{json.dumps(specification_payloads, default=str, indent=2)}\n"
    )


__all__ = ["build_meta_controller_route_prompt"]
