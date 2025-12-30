import json
import logging
import re
from typing import Any, List, Optional

from orchestrator.llm.provider import LLMProvider

from .models import AgentName, Plan, PlanStep, PlannerRequest, RouteDecision, RouteName, RouteSignals
from .policies import PolicyNotes, check_policies
from .router import build_steps, choose_route


_LEADING_FILLER_RE = re.compile(
    r"^(?:please\s+)?(?:can you|could you|would you|show me|tell me|give me|i need|i want|"
    r"i would like|let me know|what is|what are|what's|whats|find|search for|search the web for)\s+",
    re.IGNORECASE,
)
_TRAILING_FILLER_RE = re.compile(r"(?:thanks|thank you|please)[.!?]*$", re.IGNORECASE)
_WEB_DIRECTIVE_RE = re.compile(
    r"\b(?:search (?:the )?web|search online|google|bing|duckduckgo|look up|find online)\b",
    re.IGNORECASE,
)
_VISUAL_TERM_RE = re.compile(
    r"\b(?:chart|graph|plot|visualise|visualize|visual|dashboard)\b",
    re.IGNORECASE,
)


def _normalize_question(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    cleaned = _LEADING_FILLER_RE.sub("", cleaned).strip()
    cleaned = _TRAILING_FILLER_RE.sub("", cleaned).strip()
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_for_compare(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _rewrite_for_agent(agent: AgentName, question: str) -> str:
    base = _normalize_question(question)
    if not base:
        return question.strip()

    if agent == AgentName.ANALYST:
        base = _VISUAL_TERM_RE.sub("", base)
        base = _WEB_DIRECTIVE_RE.sub("", base)
        base = re.sub(r"\s+", " ", base).strip()
        return base or question.strip()

    if agent == AgentName.WEB_SEARCH:
        base = _WEB_DIRECTIVE_RE.sub("", base)
        base = re.sub(r"\s+", " ", base).strip()
        return base or question.strip()

    if agent == AgentName.DOC_RETRIEVAL:
        lowered = base.lower()
        if lowered.startswith(
            (
                "summarize",
                "summarise",
                "synthesize",
                "synthesise",
                "research",
                "analyze",
                "analyse",
            )
        ):
            return base
        return f"Synthesize key findings with citations for: {base}"

    return base


def _extract_tool_rewrites(context: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(context, dict):
        return []
    for key in ("reasoning", "routing"):
        payload = context.get(key)
        if isinstance(payload, dict):
            rewrites = payload.get("tool_rewrites")
            if isinstance(rewrites, list):
                return [item for item in rewrites if isinstance(item, dict)]
            if isinstance(rewrites, dict):
                return [rewrites]
    return []


def _summarize_plan(decision: RouteDecision, steps: List[PlanStep], request: PlannerRequest) -> str:
    question = request.question
    if decision.route == RouteName.SIMPLE_ANALYST:
        return (
            "I'll query the most relevant semantic model to answer your question, "
            "then return the result table with the exact SQL that was executed."
        )
    if decision.route == RouteName.ANALYST_THEN_VISUAL:
        return (
            "I'll run the analyst workflow to retrieve the data you asked for, "
            "then generate a visualization spec so you get both the table and an easy-to-read chart."
        )
    if decision.route == RouteName.WEB_SEARCH:
        return (
            "I'll search the web for relevant sources and return the most useful links with snippets."
        )
    if decision.route == RouteName.DEEP_RESEARCH:
        if any(step.agent == "Analyst" for step in steps):
            return (
                "I'll gather insights from the most relevant documents, synthesize the findings, "
                "and then use analytics to validate the key quantitative claims before sharing the highlights."
            )
        return (
            "I'll focus on retrieving and synthesizing the most relevant documents to answer your question, "
            "highlighting the key findings and citations for follow-up."
        )
    if decision.route == RouteName.CLARIFY:
        clarifier = next((step for step in steps if "clarifying_question" in step.input), None)
        if clarifier:
            return (
                f"I need one clarification before proceeding: {clarifier.input['clarifying_question']}"
            )
        return "I need a specific entity or time range before I can plan the right workflow."
    return f"I'll prepare a plan to address: {question}"


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


class PlanningAgent:
    """Stateless planner that returns executable plans for downstream orchestration."""

    def __init__(
        self,
        *,
        llm: Optional[LLMProvider] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.llm = llm
        self.logger = logger or logging.getLogger(__name__)

    def plan(self, request: PlannerRequest) -> Plan:
        policy_notes: PolicyNotes = check_policies(request)
        llm_plan = None
        if not self._should_bypass_llm(request):
            llm_plan = self._plan_with_llm(request, policy_notes)
        if llm_plan:
            self._apply_tool_rewrites(llm_plan, request)
            self._apply_question_rewrites(llm_plan, request)
            return llm_plan

        decision: RouteDecision = choose_route(request)
        steps: List[PlanStep] = build_steps(decision, request)
        user_summary = _summarize_plan(decision, steps, request)

        plan = Plan(
            route=decision.route.value,
            steps=steps,
            justification=decision.justification,
            user_summary=user_summary,
            assumptions=decision.assumptions,
            risks=policy_notes.risks,
        )
        self._apply_tool_rewrites(plan, request)
        self._apply_question_rewrites(plan, request)
        return plan

    @staticmethod
    def _should_bypass_llm(request: PlannerRequest) -> bool:
        if not isinstance(request.context, dict):
            return False
        for key in ("reasoning", "routing"):
            payload = request.context.get(key)
            if isinstance(payload, dict) and payload:
                return True
        return False

    def _apply_question_rewrites(self, plan: Plan, request: PlannerRequest) -> None:
        base_question = request.question
        base_norm = _normalize_for_compare(base_question)
        for step in plan.steps:
            input_payload = step.input if isinstance(step.input, dict) else {}
            if step.agent == AgentName.ANALYST.value:
                current = str(input_payload.get("question") or base_question)
                current_norm = _normalize_for_compare(current)
                if not current.strip() or current_norm == base_norm:
                    input_payload["original_question"] = base_question
                    input_payload["question"] = _rewrite_for_agent(AgentName.ANALYST, base_question)
                step.input = input_payload
                continue
            if step.agent == AgentName.WEB_SEARCH.value:
                current = str(input_payload.get("query") or base_question)
                current_norm = _normalize_for_compare(current)
                if not current.strip() or current_norm == base_norm:
                    input_payload["original_question"] = base_question
                    input_payload["query"] = _rewrite_for_agent(AgentName.WEB_SEARCH, base_question)
                step.input = input_payload
                continue
            if step.agent == AgentName.DOC_RETRIEVAL.value:
                current = str(input_payload.get("question") or base_question)
                current_norm = _normalize_for_compare(current)
                if not current.strip() or current_norm == base_norm:
                    input_payload["original_question"] = base_question
                    input_payload["question"] = _rewrite_for_agent(AgentName.DOC_RETRIEVAL, base_question)
                step.input = input_payload

    def _apply_tool_rewrites(self, plan: Plan, request: PlannerRequest) -> None:
        rewrites = _extract_tool_rewrites(request.context)
        if not rewrites:
            return

        used_steps: set[str] = set()
        for rewrite in rewrites:
            agent = self._normalize_agent_name(
                rewrite.get("agent") or rewrite.get("tool") or rewrite.get("target")
            )
            if not agent:
                continue

            step_id = rewrite.get("step_id") or rewrite.get("step") or rewrite.get("id")
            target_step: Optional[PlanStep] = None
            if isinstance(step_id, str) and step_id.strip():
                target_step = next(
                    (step for step in plan.steps if step.id == step_id and step.agent == agent.value),
                    None,
                )
            if not target_step:
                for step in plan.steps:
                    if step.agent != agent.value:
                        continue
                    if step.id in used_steps:
                        continue
                    target_step = step
                    break

            if not target_step:
                continue

            input_payload = target_step.input if isinstance(target_step.input, dict) else {}
            question = rewrite.get("question") or rewrite.get("query") or rewrite.get("rewritten_question")
            if isinstance(question, str) and question.strip():
                if agent == AgentName.WEB_SEARCH:
                    input_payload["query"] = question.strip()
                else:
                    input_payload["question"] = question.strip()
                    input_payload.setdefault("original_question", request.question)

            follow_up = rewrite.get("follow_up") or rewrite.get("instruction")
            if isinstance(follow_up, str) and follow_up.strip():
                input_payload["follow_up"] = follow_up.strip()

            source_step_ref = rewrite.get("source_step_ref") or rewrite.get("source_step")
            if isinstance(source_step_ref, str) and source_step_ref.strip():
                input_payload["source_step_ref"] = source_step_ref.strip()

            target_step.input = input_payload
            used_steps.add(target_step.id)

    def _plan_with_llm(
        self,
        request: PlannerRequest,
        policy_notes: PolicyNotes,
    ) -> Optional[Plan]:
        if not self.llm:
            return None

        prompt = self._build_llm_prompt(request, policy_notes)
        try:
            response = self.llm.complete(prompt, temperature=0.0, max_tokens=900)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("PlanningAgent LLM call failed: %s", exc)
            return None

        payload = self._parse_llm_payload(str(response))
        if not payload:
            return None

        plan = self._coerce_llm_plan(payload, request, policy_notes)
        if not plan:
            return None

        self.logger.info("PlanningAgent selected LLM-generated plan with route '%s'", plan.route)
        return plan

    def _build_llm_prompt(self, request: PlannerRequest, policy_notes: PolicyNotes) -> str:
        constraints_payload = request.constraints.model_dump()
        context_payload = request.context or {}
        available_agents = context_payload.get("available_agents")
        semantic_models = context_payload.get("semantic_models")
        semantic_models_count = context_payload.get("semantic_models_count")
        context_core = {
            key: value
            for key, value in context_payload.items()
            if key
            not in (
                "available_agents",
                "semantic_models",
                "semantic_models_count",
                "semantic_models_truncated",
            )
        }
        prompt_sections = [
            "You are the planning agent for an analytics orchestrator.",
            "Return ONLY a JSON object with keys: route, steps, justification, user_summary, assumptions.",
            "route must be one of: SimpleAnalyst, AnalystThenVisual, WebSearch, DeepResearch, Clarify.",
            "steps must be a list of objects with keys: id, agent, input, expected_output.",
            "agent must be one of: Analyst, Visual, WebSearch, DocRetrieval, Clarify.",
            "Respect the constraints; never exceed max_steps and never use a disabled tool.",
            "If route is Clarify, include exactly one Clarify step with clarifying_question in input.",
            "If you include a Visual step, set rows_ref to the Analyst step id.",
            f"Question: {request.question}",
            f"Context (JSON): {json.dumps(context_core, default=str, ensure_ascii=True)}",
            f"Constraints (JSON): {json.dumps(constraints_payload, default=str, ensure_ascii=True)}",
        ]
        if "available_agents" in context_payload:
            prompt_sections.append(
                f"Available agents (JSON): {json.dumps(available_agents, default=str, ensure_ascii=True)}"
            )
        if "semantic_models" in context_payload:
            prompt_sections.append(
                f"Available semantic models (JSON): {json.dumps(semantic_models, default=str, ensure_ascii=True)}"
            )
        if semantic_models_count is not None:
            prompt_sections.append(f"Semantic model count: {semantic_models_count}")
            if context_payload.get("semantic_models_truncated"):
                prompt_sections.append(
                    "Note: semantic_models list truncated; choose the best match or ask for a specific model if needed."
                )
        prompt_sections.append(f"Policy risks: {policy_notes.risks or []}")
        return "\n".join(prompt_sections)

    def _parse_llm_payload(self, response: str) -> Optional[dict[str, Any]]:
        blob = _extract_json_blob(response)
        if not blob:
            return None
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _coerce_llm_plan(
        self,
        payload: dict[str, Any],
        request: PlannerRequest,
        policy_notes: PolicyNotes,
    ) -> Optional[Plan]:
        route_value = payload.get("route") or payload.get("plan_route") or payload.get("route_name")
        route = self._normalize_route_name(route_value)
        if not route:
            return None
        if not self._is_route_available(route, request):
            return None

        raw_steps = payload.get("steps")
        steps = self._coerce_steps(raw_steps, request)
        if not steps:
            return None
        if route == RouteName.CLARIFY:
            if len(steps) != 1 or steps[0].agent != AgentName.CLARIFY.value:
                return None
            if "clarifying_question" not in steps[0].input:
                return None

        justification = str(payload.get("justification") or "").strip()
        if not justification:
            justification = f"LLM planned route '{route.value}' based on the request and constraints."

        assumptions = payload.get("assumptions")
        if isinstance(assumptions, list):
            assumptions_list = [str(item) for item in assumptions if str(item).strip()]
        else:
            assumptions_list = []

        user_summary = str(payload.get("user_summary") or payload.get("summary") or "").strip()
        if not user_summary:
            fallback_decision = RouteDecision(
                route=route,
                justification=justification,
                signals=RouteSignals(),
            )
            user_summary = _summarize_plan(fallback_decision, steps, request)

        return Plan(
            route=route.value,
            steps=steps,
            justification=justification,
            user_summary=user_summary,
            assumptions=assumptions_list,
            risks=policy_notes.risks,
        )

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

    @staticmethod
    def _agent_allowed(agent: AgentName, request: PlannerRequest) -> bool:
        constraints = request.constraints
        if agent in (AgentName.ANALYST, AgentName.VISUAL):
            return constraints.allow_sql_analyst
        if agent == AgentName.WEB_SEARCH:
            return constraints.allow_web_search
        if agent == AgentName.DOC_RETRIEVAL:
            return constraints.allow_deep_research
        if agent == AgentName.CLARIFY:
            return True
        return False

    @staticmethod
    def _is_route_available(route: RouteName, request: PlannerRequest) -> bool:
        constraints = request.constraints
        if route == RouteName.CLARIFY:
            return True
        if route == RouteName.SIMPLE_ANALYST:
            return constraints.allow_sql_analyst and constraints.max_steps >= 1
        if route == RouteName.ANALYST_THEN_VISUAL:
            return constraints.allow_sql_analyst and constraints.max_steps >= 2
        if route == RouteName.WEB_SEARCH:
            return constraints.allow_web_search and constraints.max_steps >= 1
        if route == RouteName.DEEP_RESEARCH:
            return constraints.allow_deep_research and constraints.max_steps >= 1
        return False

    def _coerce_steps(
        self,
        raw_steps: Any,
        request: PlannerRequest,
    ) -> Optional[List[PlanStep]]:
        if not isinstance(raw_steps, list) or not raw_steps:
            return None

        steps: List[PlanStep] = []
        used_ids: set[str] = set()
        id_map: dict[str, str] = {}

        for index, raw_step in enumerate(raw_steps, start=1):
            if not isinstance(raw_step, dict):
                return None
            agent_value = self._normalize_agent_name(raw_step.get("agent"))
            if not agent_value:
                return None
            if not self._agent_allowed(agent_value, request):
                return None

            raw_id = raw_step.get("id")
            step_id = str(raw_id).strip() if isinstance(raw_id, str) and raw_id.strip() else f"step-{index}"
            if step_id in used_ids:
                return None
            used_ids.add(step_id)
            if isinstance(raw_id, str) and raw_id.strip():
                id_map[raw_id] = step_id

            input_payload = raw_step.get("input") if isinstance(raw_step.get("input"), dict) else {}
            expected_output = (
                raw_step.get("expected_output")
                if isinstance(raw_step.get("expected_output"), dict)
                else {}
            )
            steps.append(
                PlanStep(
                    id=step_id,
                    agent=agent_value.value,
                    input=input_payload,
                    expected_output=expected_output,
                )
            )

        if len(steps) > request.constraints.max_steps:
            return None

        self._rewrite_step_references(steps, id_map)
        return steps

    @staticmethod
    def _rewrite_step_references(steps: List[PlanStep], id_map: dict[str, str]) -> None:
        valid_ids = {step.id for step in steps}
        last_analyst_id: Optional[str] = None
        last_web_id: Optional[str] = None
        last_doc_id: Optional[str] = None

        for step in steps:
            if step.agent == AgentName.ANALYST.value:
                last_analyst_id = step.id
            if step.agent == AgentName.WEB_SEARCH.value:
                last_web_id = step.id
            if step.agent == AgentName.DOC_RETRIEVAL.value:
                last_doc_id = step.id

            input_payload = step.input if isinstance(step.input, dict) else {}
            for ref_key in ("rows_ref", "schema_ref", "source_step_ref", "step_ref"):
                ref_value = input_payload.get(ref_key)
                if isinstance(ref_value, str) and ref_value in id_map:
                    input_payload[ref_key] = id_map[ref_value]

            if step.agent == AgentName.VISUAL.value and last_analyst_id:
                if input_payload.get("rows_ref") not in valid_ids:
                    input_payload["rows_ref"] = last_analyst_id
                if input_payload.get("schema_ref") not in valid_ids:
                    input_payload["schema_ref"] = last_analyst_id

            if step.agent == AgentName.DOC_RETRIEVAL.value and last_web_id:
                if input_payload.get("source_step_ref") not in valid_ids:
                    input_payload["source_step_ref"] = last_web_id

            if step.agent == AgentName.ANALYST.value and last_doc_id:
                if input_payload.get("source_step_ref") not in valid_ids:
                    input_payload["source_step_ref"] = last_doc_id

            step.input = input_payload


__all__ = ["PlanningAgent"]
