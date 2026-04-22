"""LLM-guided meta-controller gateway for the Langbridge AI package."""
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from langbridge.ai.agents.presentation import PresentationAgent
from langbridge.ai.base import (
    AgentIOContract,
    AgentResult,
    AgentResultStatus,
    AgentRoutingSpec,
    AgentSpecification,
    AgentTask,
    AgentTaskKind,
    BaseAgent,
)
from langbridge.ai.events import AIEventEmitter, AIEventSource
from langbridge.ai.llm.base import LLMProvider
from langbridge.ai.modes import normalize_analyst_task_input
from langbridge.ai.orchestration.execution import PlanExecutionState
from langbridge.ai.orchestration.meta_controller_prompts import build_meta_controller_route_prompt
from langbridge.ai.orchestration.plan_review import PlanReviewAction, PlanReviewAgent, PlanReviewDecision
from langbridge.ai.orchestration.planner import ExecutionPlan, PlannerAgent, PlanStep
from langbridge.ai.orchestration.verification import AgentVerifier, VerificationOutcome
from langbridge.ai.registry import AgentRegistry


class MetaControllerAction(str, Enum):
    direct = "direct"
    plan = "plan"
    clarify = "clarify"
    abort = "abort"


class MetaControllerDecision(BaseModel):
    action: MetaControllerAction
    rationale: str
    agent_name: str | None = None
    task_kind: AgentTaskKind | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    clarification_question: str | None = None
    plan_guidance: str | None = None


class MetaControllerRun(BaseModel):
    execution_mode: str | None = None
    status: str = "completed"
    plan: ExecutionPlan
    step_results: list[dict[str, Any]] = Field(default_factory=list)
    verification: list[VerificationOutcome] = Field(default_factory=list)
    review_decisions: list[PlanReviewDecision] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
    presentation: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class MetaControllerAgent(AIEventSource, BaseAgent):
    """Agent gateway that asks an LLM for route guidance, then executes PEV."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        llm_provider: LLMProvider,
        presentation_agent: PresentationAgent,
        planner: PlannerAgent | None = None,
        verifier: AgentVerifier | None = None,
        plan_review: PlanReviewAgent | None = None,
        max_iterations: int = 8,
        max_replans: int = 2,
        max_step_retries: int = 1,
        event_emitter: AIEventEmitter | None = None,
    ) -> None:
        super().__init__(event_emitter=event_emitter)
        self._registry = registry
        self._llm = llm_provider
        self._planner = planner or PlannerAgent(llm_provider=llm_provider)
        self._verifier = verifier or AgentVerifier()
        self._plan_review = plan_review or PlanReviewAgent()
        self._presentation_agent = presentation_agent
        self._max_iterations = max(1, int(max_iterations))
        self._max_replans = max(0, int(max_replans))
        self._max_step_retries = max(0, int(max_step_retries))

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="meta-controller",
            description="Gateway agent that reads agent specifications, asks an LLM for routing guidance, and executes PEV.",
            task_kinds=[AgentTaskKind.orchestration],
            capabilities=[
                "read agent specifications",
                "ask LLM for route guidance",
                "ask clarifying questions",
                "invoke planner",
                "execute PEV loop",
            ],
            constraints=["Does not perform domain analysis directly."],
            routing=AgentRoutingSpec(keywords=["route", "plan", "execute"], direct_threshold=99),
            can_execute_direct=False,
            output_contract=AgentIOContract(required_keys=["run"]),
        )

    async def execute(self, task: AgentTask) -> AgentResult:
        run = await self.handle(
            question=task.question,
            context=task.context,
            force_plan=bool(task.input.get("force_plan")),
        )
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"run": run.model_dump(mode="json")},
        )

    async def handle(
        self,
        *,
        question: str,
        context: dict[str, Any] | None = None,
        force_plan: bool = False,
    ) -> MetaControllerRun:
        runtime_context = dict(context or {})
        specifications = self._available_specifications()
        await self._emit_ai_event(
            event_type="MetaControllerStarted",
            message="Reading agent specifications.",
            source="meta-controller",
            details={"available_agents": [specification.name for specification in specifications]},
        )

        decision = await self._route_with_llm(
            question=question,
            context=runtime_context,
            specifications=self._registry.specifications(),
            force_plan=force_plan,
        )
        await self._emit_ai_event(
            event_type="AgentRouteSelected",
            message=decision.rationale,
            source="meta-controller",
            details={
                "action": decision.action.value,
                "agent_name": decision.agent_name,
                "task_kind": decision.task_kind.value if decision.task_kind else None,
            },
        )

        if decision.action == MetaControllerAction.clarify:
            return await self._finish_before_execution(
                execution_mode=None,
                route="clarification",
                question=question,
                context={
                    **runtime_context,
                    "clarification_question": decision.clarification_question or decision.rationale,
                },
                presentation_mode="clarification",
                diagnostics={
                    "route_decision": decision.model_dump(mode="json"),
                    "available_agents": [specification.name for specification in specifications],
                    "stop_reason": "clarification",
                },
                rationale=decision.rationale,
            )

        if decision.action == MetaControllerAction.abort:
            return await self._finish_before_execution(
                execution_mode=None,
                route="abort",
                question=question,
                context={**runtime_context, "error": decision.rationale},
                presentation_mode="failure",
                diagnostics={
                    "route_decision": decision.model_dump(mode="json"),
                    "available_agents": [specification.name for specification in specifications],
                    "stop_reason": "abort",
                },
                rationale=decision.rationale,
            )

        if decision.action == MetaControllerAction.direct:
            target = self._resolve_direct_target(decision)
            input_payload = decision.input
            if (decision.task_kind or target.task_kinds[0]) == AgentTaskKind.analyst:
                input_payload = normalize_analyst_task_input(
                    input_payload,
                    requested_mode=runtime_context.get("requested_agent_mode") or runtime_context.get("agent_mode"),
                )
            plan = self._build_direct_plan(
                question=question,
                specification=target,
                task_kind=decision.task_kind,
                input_payload=input_payload,
                rationale=decision.rationale,
            )
            return await self._execute_plan(
                execution_mode="direct",
                plan=plan,
                question=question,
                context=runtime_context,
                diagnostics={
                    "selected_agent": target.name,
                    "route_decision": decision.model_dump(mode="json"),
                    "available_agents": [specification.name for specification in specifications],
                },
            )

        if decision.action != MetaControllerAction.plan:
            raise ValueError(f"Meta-controller LLM selected unsupported action: {decision.action}")

        plan_context = {
            **runtime_context,
            "plan_guidance": decision.plan_guidance or decision.rationale,
            "route_decision": decision.model_dump(mode="json"),
        }
        await self._emit_ai_event(
            event_type="PlannerStarted",
            message="Building execution plan.",
            source="planner",
        )
        plan = await self._planner.build_plan(
            question=question,
            context=plan_context,
            specifications=self._registry.specifications(),
        )
        await self._emit_ai_event(
            event_type="PlanCreated",
            message=f"Created plan with {len(plan.steps)} step(s).",
            source="planner",
            details={"route": plan.route, "step_count": len(plan.steps)},
        )
        return await self._execute_plan(
            execution_mode="planned",
            plan=plan,
            question=question,
            context=plan_context,
            diagnostics={
                "planner": self._planner.specification.name,
                "route_decision": decision.model_dump(mode="json"),
                "available_agents": [specification.name for specification in specifications],
            },
        )

    async def _route_with_llm(
        self,
        *,
        question: str,
        context: dict[str, Any],
        specifications: list[AgentSpecification],
        force_plan: bool,
    ) -> MetaControllerDecision:
        await self._emit_ai_event(
            event_type="AgentRoutingStarted",
            message="Asking for route guidance.",
            source="meta-controller",
        )
        prompt = build_meta_controller_route_prompt(
            question=question,
            context=context,
            force_plan=force_plan,
            requested_agent_mode=str(context.get("requested_agent_mode") or context.get("agent_mode") or ""),
            specification_payloads=[self._spec_payload(item) for item in specifications],
        )
        raw = await self._llm.acomplete(prompt, temperature=0.0, max_tokens=700)
        parsed = self._parse_json_object(raw)
        for key in ("agent_name", "task_kind", "clarification_question", "plan_guidance"):
            if parsed.get(key) in ("", None):
                parsed[key] = None
        decision = MetaControllerDecision.model_validate(parsed)
        decision = self._normalize_route_decision(decision, context=context)
        if force_plan and decision.action == MetaControllerAction.direct:
            raise ValueError("Meta-controller LLM selected direct route despite force_plan.")
        return decision

    def _available_specifications(self) -> list[AgentSpecification]:
        return [
            self.specification,
            self._planner.specification,
            self._plan_review.specification,
            self._presentation_agent.specification,
            *self._registry.specifications(),
        ]

    def _resolve_direct_target(self, decision: MetaControllerDecision) -> AgentSpecification:
        if not decision.agent_name:
            raise ValueError("Meta-controller direct route requires agent_name.")
        specification = self._registry.get(decision.agent_name).specification
        if decision.task_kind is not None and not specification.supports(decision.task_kind):
            raise ValueError(
                f"Meta-controller selected unsupported task kind '{decision.task_kind.value}' for {specification.name}."
            )
        return specification

    @staticmethod
    def _normalize_route_decision(
        decision: MetaControllerDecision,
        *,
        context: dict[str, Any],
    ) -> MetaControllerDecision:
        if decision.action != MetaControllerAction.direct:
            return decision
        if decision.task_kind != AgentTaskKind.analyst:
            return decision
        requested_mode = context.get("requested_agent_mode") or context.get("agent_mode")
        return decision.model_copy(
            update={
                "input": normalize_analyst_task_input(
                    decision.input,
                    requested_mode=requested_mode,
                )
            }
        )

    @staticmethod
    def _build_direct_plan(
        *,
        question: str,
        specification: AgentSpecification,
        task_kind: AgentTaskKind | None = None,
        input_payload: dict[str, Any] | None = None,
        rationale: str | None = None,
    ) -> ExecutionPlan:
        return ExecutionPlan(
            route=f"direct:{specification.name}",
            steps=[
                PlanStep(
                    step_id="step-1",
                    agent_name=specification.name,
                    task_kind=task_kind or specification.task_kinds[0],
                    question=question,
                    input=input_payload or {},
                    expected_output=specification.output_contract,
                )
            ],
            rationale=rationale or "Meta-controller LLM selected one direct agent.",
            requires_pev=True,
        )

    @staticmethod
    def _build_terminal_plan(*, route: str, rationale: str) -> ExecutionPlan:
        return ExecutionPlan(route=route, steps=[], rationale=rationale, requires_pev=False)

    async def _finish_before_execution(
        self,
        *,
        execution_mode: str | None,
        route: str,
        question: str,
        context: dict[str, Any],
        presentation_mode: str,
        diagnostics: dict[str, Any],
        rationale: str,
    ) -> MetaControllerRun:
        final = await self._present(question=question, context=context, mode=presentation_mode)
        plan = self._build_terminal_plan(route=route, rationale=rationale)
        return MetaControllerRun(
            execution_mode=execution_mode,
            status=self._status_for_presentation_mode(presentation_mode),
            plan=plan,
            final_result=final,
            presentation=final,
            diagnostics=diagnostics,
        )

    async def _execute_plan(
        self,
        *,
        execution_mode: str,
        plan: ExecutionPlan,
        question: str,
        context: dict[str, Any],
        diagnostics: dict[str, Any],
    ) -> MetaControllerRun:
        if not plan.steps:
            if plan.clarification_question:
                final = await self._present(
                    question=question,
                    context={**context, "clarification_question": plan.clarification_question},
                    mode="clarification",
                )
                return MetaControllerRun(
                    execution_mode=self._execution_mode_from_plan(plan=plan, requested_mode=execution_mode),
                    status="clarification_needed",
                    plan=plan,
                    final_result=final,
                    presentation=final,
                    diagnostics={
                        **diagnostics,
                        "stop_reason": "clarification",
                        "clarification_source": "planner",
                    },
                )
            await self._emit_ai_event(
                event_type="PlanFailed",
                message="Planner returned no executable steps.",
                source="meta-controller",
            )
            failed = VerificationOutcome(
                passed=False,
                step_id="plan",
                agent_name="planner",
                message="Planner returned no executable steps.",
            )
            final = await self._present(
                question=question,
                context={**context, "error": failed.message},
                mode="failure",
            )
            return MetaControllerRun(
                execution_mode=self._execution_mode_from_plan(plan=plan, requested_mode=execution_mode),
                status="failed",
                plan=plan,
                verification=[failed],
                final_result=final,
                presentation=final,
                diagnostics=diagnostics,
            )

        state = PlanExecutionState(
            original_question=question,
            current_plan=plan,
            context=dict(context),
            max_iterations=self._max_iterations,
            max_replans=self._max_replans,
            max_step_retries=self._max_step_retries,
        )

        while state.iteration < state.max_iterations:
            step = state.next_pending_step()
            if step is None:
                return await self._finalize(
                    execution_mode=execution_mode,
                    state=state,
                    question=question,
                    context=context,
                    diagnostics={**diagnostics, "stop_reason": "plan_completed"},
                )

            agent = self._registry.get(step.agent_name)
            await self._emit_ai_event(
                event_type="PlanStepStarted",
                message=f"Running {step.agent_name}.",
                source=step.agent_name,
                details={
                    "step_id": step.step_id,
                    "agent_name": step.agent_name,
                    "task_kind": step.task_kind.value,
                },
            )
            task = AgentTask(
                task_id=step.step_id,
                task_kind=step.task_kind,
                question=step.question or question,
                input=step.input,
                context={**context, "step_results": state.step_results_payload()},
                expected_output=step.expected_output,
            )
            result = await agent.execute(task)
            await self._emit_ai_event(
                event_type="PlanStepCompleted",
                message=f"{step.agent_name} returned {result.status.value}.",
                source=step.agent_name,
                details={
                    "step_id": step.step_id,
                    "agent_name": step.agent_name,
                    "status": result.status.value,
                },
            )
            verification = self._verifier.verify(step=step, result=result)
            await self._emit_ai_event(
                event_type="VerificationCompleted",
                message=verification.message,
                source="verifier",
                details={
                    "step_id": verification.step_id,
                    "agent_name": verification.agent_name,
                    "passed": verification.passed,
                    "missing_output_keys": list(verification.missing_output_keys),
                },
            )
            state.record(step=step, result=result, verification=verification)

            decision = self._plan_review.review(state)
            state.record_review(decision)
            await self._emit_ai_event(
                event_type="PlanReviewDecision",
                message=decision.rationale,
                source="plan-review",
                details={
                    "action": decision.action.value,
                    "retry_step_id": decision.retry_step_id,
                },
            )

            if decision.action == PlanReviewAction.continue_plan:
                if state.iteration >= state.max_iterations:
                    return await self._finish_iteration_exhausted(
                        execution_mode=execution_mode,
                        state=state,
                        question=question,
                        context=context,
                        diagnostics=diagnostics,
                        decision=decision,
                    )
                continue
            if decision.action == PlanReviewAction.retry_step:
                if state.iteration >= state.max_iterations:
                    return await self._finish_iteration_exhausted(
                        execution_mode=execution_mode,
                        state=state,
                        question=question,
                        context=context,
                        diagnostics=diagnostics,
                        decision=decision,
                    )
                state.increment_retry(decision.retry_step_id or step.step_id)
                await self._emit_ai_event(
                    event_type="PlanRetryScheduled",
                    message=f"Retrying {decision.retry_step_id or step.step_id}.",
                    source="plan-review",
                    details={"step_id": decision.retry_step_id or step.step_id},
                )
                continue
            if decision.action == PlanReviewAction.revise_plan:
                if state.iteration >= state.max_iterations:
                    return await self._finish_iteration_exhausted(
                        execution_mode=execution_mode,
                        state=state,
                        question=question,
                        context=context,
                        diagnostics=diagnostics,
                        decision=decision,
                    )
                state.replan_count += 1
                state.context = {**state.context, **decision.updated_context}
                await self._emit_ai_event(
                    event_type="PlanReplanStarted",
                    message="Revising execution plan.",
                    source="planner",
                    details={"replan_count": state.replan_count},
                )
                state.current_plan = await self._planner.replan(
                    state=state,
                    context_updates=decision.updated_context,
                    specifications=self._registry.specifications(),
                )
                await self._emit_ai_event(
                    event_type="PlanReplanCreated",
                    message=f"Revised plan has {len(state.current_plan.steps)} step(s).",
                    source="planner",
                    details={"step_count": len(state.current_plan.steps)},
                )
                continue
            if decision.action == PlanReviewAction.ask_clarification:
                return await self._finish_with_mode(
                    execution_mode=execution_mode,
                    state=state,
                    question=question,
                    context={
                        **context,
                        "clarification_question": decision.clarification_question or decision.rationale,
                    },
                    presentation_mode="clarification",
                    diagnostics={**diagnostics, "stop_reason": "clarification"},
                )
            if decision.action == PlanReviewAction.abort:
                return await self._finish_with_mode(
                    execution_mode=execution_mode,
                    state=state,
                    question=question,
                    context={**context, "error": decision.rationale},
                    presentation_mode="failure",
                    diagnostics={**diagnostics, "stop_reason": "abort"},
                )
            if decision.action == PlanReviewAction.finalize:
                return await self._finalize(
                    execution_mode=execution_mode,
                    state=state,
                    question=question,
                    context=context,
                    diagnostics={**diagnostics, "stop_reason": "finalize"},
                )

        return await self._finish_iteration_exhausted(
            execution_mode=execution_mode,
            state=state,
            question=question,
            context=context,
            diagnostics=diagnostics,
            decision=None,
        )

    async def _finalize(
        self,
        *,
        execution_mode: str,
        state: PlanExecutionState,
        question: str,
        context: dict[str, Any],
        diagnostics: dict[str, Any],
    ) -> MetaControllerRun:
        return await self._finish_with_mode(
            execution_mode=execution_mode,
            state=state,
            question=question,
            context=context,
            presentation_mode="final",
            diagnostics=diagnostics,
        )

    async def _finish_with_mode(
        self,
        *,
        execution_mode: str,
        state: PlanExecutionState,
        question: str,
        context: dict[str, Any],
        presentation_mode: str,
        diagnostics: dict[str, Any],
    ) -> MetaControllerRun:
        final = await self._present(
            question=question,
            context={
                **context,
                "step_results": state.step_results_payload(),
                "plan": state.current_plan.model_dump(mode="json"),
            },
            mode=presentation_mode,
        )
        return self._build_run(
            execution_mode=execution_mode,
            state=state,
            final=final,
            diagnostics=diagnostics,
            status=self._status_for_presentation_mode(presentation_mode),
        )

    async def _finish_iteration_exhausted(
        self,
        *,
        execution_mode: str,
        state: PlanExecutionState,
        question: str,
        context: dict[str, Any],
        diagnostics: dict[str, Any],
        decision: PlanReviewDecision | None,
    ) -> MetaControllerRun:
        terminal_error = self._iteration_exhausted_error_message(state=state, decision=decision)
        return await self._finish_with_mode(
            execution_mode=execution_mode,
            state=state,
            question=question,
            context={**context, "error": terminal_error},
            presentation_mode="failure",
            diagnostics={
                **diagnostics,
                "stop_reason": "max_iterations",
                "terminal_error": terminal_error,
            },
        )

    async def _present(
        self,
        *,
        question: str,
        context: dict[str, Any],
        mode: str,
    ) -> dict[str, Any]:
        task = AgentTask(
            task_id="presentation",
            task_kind=AgentTaskKind.presentation,
            question=question,
            input={"mode": mode},
            context=context,
            expected_output=self._presentation_agent.specification.output_contract,
        )
        await self._emit_ai_event(
            event_type="PresentationStarted",
            message="Preparing final response.",
            source="presentation",
            details={"mode": mode},
        )
        result = await self._presentation_agent.execute(task)
        await self._emit_ai_event(
            event_type="PresentationCompleted",
            message="Final response prepared.",
            source="presentation",
            details={"status": result.status.value},
        )
        response = result.output.get("response")
        return response if isinstance(response, dict) else result.output

    @staticmethod
    def _build_run(
        *,
        execution_mode: str,
        state: PlanExecutionState,
        final: dict[str, Any],
        diagnostics: dict[str, Any],
        status: str,
    ) -> MetaControllerRun:
        resolved_execution_mode = MetaControllerAgent._execution_mode_from_plan(
            plan=state.current_plan,
            requested_mode=execution_mode,
        )
        return MetaControllerRun(
            execution_mode=resolved_execution_mode,
            status=status,
            plan=state.current_plan,
            step_results=state.step_results_payload(),
            verification=list(state.verifier_outcomes),
            review_decisions=[
                PlanReviewDecision.model_validate(item) for item in state.review_decisions
            ],
            final_result=final,
            presentation=final,
            diagnostics={
                **diagnostics,
                "iterations": state.iteration,
                "replan_count": state.replan_count,
            },
        )

    @staticmethod
    def _execution_mode_from_plan(*, plan: ExecutionPlan, requested_mode: str) -> str | None:
        route = str(plan.route or "").strip().lower()
        if route.startswith("direct:"):
            return "direct"
        if route.startswith("planned"):
            return "planned"
        if plan.steps:
            return "planned"
        if requested_mode in {"direct", "planned"}:
            return requested_mode
        return None

    @staticmethod
    def _status_for_presentation_mode(presentation_mode: str) -> str:
        normalized = str(presentation_mode or "final").strip().lower()
        if normalized == "clarification":
            return "clarification_needed"
        if normalized == "failure":
            return "failed"
        return "completed"

    @staticmethod
    def _iteration_exhausted_error_message(
        *,
        state: PlanExecutionState,
        decision: PlanReviewDecision | None,
    ) -> str:
        latest = state.latest_record
        if latest is not None:
            if latest.verification.message:
                return latest.verification.message
            if latest.result.error:
                return latest.result.error
        if decision is not None and decision.rationale:
            return decision.rationale
        return "Meta-controller reached max iterations before finalizing."

    @staticmethod
    def _spec_payload(specification: AgentSpecification) -> dict[str, Any]:
        return {
            "name": specification.name,
            "description": specification.description,
            "task_kinds": [item.value for item in specification.task_kinds],
            "capabilities": list(specification.capabilities),
            "constraints": list(specification.constraints),
            "tools": [tool.model_dump(mode="json") for tool in specification.tools],
            "input_contract": specification.input_contract.model_dump(mode="json"),
            "output_contract": specification.output_contract.model_dump(mode="json"),
            "can_execute_direct": specification.can_execute_direct,
            "metadata": dict(specification.metadata or {}),
        }

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Meta-controller LLM response did not contain a JSON object.")
        parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("Meta-controller LLM response JSON must be an object.")
        return parsed


__all__ = ["MetaControllerAction", "MetaControllerAgent", "MetaControllerDecision", "MetaControllerRun"]
