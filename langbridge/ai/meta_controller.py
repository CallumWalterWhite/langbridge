"""Meta-controller gateway for the Langbridge AI package."""
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
from langbridge.ai.execution import PlanExecutionState
from langbridge.ai.plan_review import PlanReviewAction, PlanReviewAgent, PlanReviewDecision
from langbridge.ai.planner import ExecutionPlan, PlannerAgent, PlanStep
from langbridge.ai.registry import AgentRegistry
from langbridge.ai.routing import SpecificationRouter
from langbridge.ai.verification import AgentVerifier, VerificationOutcome


class MetaControllerRun(BaseModel):
    mode: str
    plan: ExecutionPlan
    step_results: list[dict[str, Any]] = Field(default_factory=list)
    verification: list[VerificationOutcome] = Field(default_factory=list)
    review_decisions: list[PlanReviewDecision] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
    presentation: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class MetaControllerAgent(BaseAgent):
    """Agent gateway that routes direct work or invokes planner + PEV."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        planner: PlannerAgent | None = None,
        verifier: AgentVerifier | None = None,
        plan_review: PlanReviewAgent | None = None,
        presentation_agent: PresentationAgent,
        router: SpecificationRouter | None = None,
        max_iterations: int = 8,
        max_replans: int = 2,
        max_step_retries: int = 1,
    ) -> None:
        self._registry = registry
        self._planner = planner or PlannerAgent()
        self._verifier = verifier or AgentVerifier()
        self._plan_review = plan_review or PlanReviewAgent()
        self._presentation_agent = presentation_agent
        self._router = router or SpecificationRouter()
        self._max_iterations = max(1, int(max_iterations))
        self._max_replans = max(0, int(max_replans))
        self._max_step_retries = max(0, int(max_step_retries))

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="meta-controller",
            description="Gateway agent that reads agent specifications, routes direct work, or plans PEV execution.",
            task_kinds=[AgentTaskKind.orchestration],
            capabilities=[
                "read agent specifications",
                "route direct tasks",
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

        direct_match = None
        if not force_plan:
            direct_match = self._router.direct_match(
                question=question,
                specifications=self._registry.specifications(),
            )

        if direct_match is not None:
            plan = self._build_direct_plan(question=question, specification=direct_match.specification)
            return await self._execute_plan(
                mode="direct",
                plan=plan,
                question=question,
                context=runtime_context,
                diagnostics={
                    "selected_agent": direct_match.specification.name,
                    "route_score": direct_match.score,
                    "available_agents": [specification.name for specification in specifications],
                },
            )

        plan = self._planner.build_plan(
            question=question,
            context=runtime_context,
            specifications=self._registry.specifications(),
        )
        return await self._execute_plan(
            mode="planned",
            plan=plan,
            question=question,
            context=runtime_context,
            diagnostics={
                "planner": self._planner.specification.name,
                "available_agents": [specification.name for specification in specifications],
            },
        )

    def _available_specifications(self) -> list[AgentSpecification]:
        return [
            self.specification,
            self._planner.specification,
            self._plan_review.specification,
            self._presentation_agent.specification,
            *self._registry.specifications(),
        ]

    @staticmethod
    def _build_direct_plan(*, question: str, specification: AgentSpecification) -> ExecutionPlan:
        return ExecutionPlan(
            route=f"direct:{specification.name}",
            steps=[
                PlanStep(
                    step_id="step-1",
                    agent_name=specification.name,
                    task_kind=specification.task_kinds[0],
                    question=question,
                    expected_output=specification.output_contract,
                )
            ],
            rationale="Meta-controller selected one safe direct agent from structured specifications.",
            requires_pev=True,
        )

    async def _execute_plan(
        self,
        *,
        mode: str,
        plan: ExecutionPlan,
        question: str,
        context: dict[str, Any],
        diagnostics: dict[str, Any],
    ) -> MetaControllerRun:
        if not plan.steps:
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
                mode=mode,
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
                    mode=mode,
                    state=state,
                    question=question,
                    context=context,
                    diagnostics={**diagnostics, "stop_reason": "plan_completed"},
                )

            agent = self._registry.get(step.agent_name)
            task = AgentTask(
                task_id=step.step_id,
                task_kind=step.task_kind,
                question=question,
                input=step.input,
                context={**context, "step_results": state.step_results_payload()},
                expected_output=step.expected_output,
            )
            result = await agent.execute(task)
            verification = self._verifier.verify(step=step, result=result)
            state.record(step=step, result=result, verification=verification)

            decision = self._plan_review.review(state)
            state.record_review(decision)

            if decision.action == PlanReviewAction.continue_plan:
                continue
            if decision.action == PlanReviewAction.retry_step:
                state.increment_retry(decision.retry_step_id or step.step_id)
                continue
            if decision.action == PlanReviewAction.revise_plan:
                state.replan_count += 1
                state.context = {**state.context, **decision.updated_context}
                state.current_plan = self._planner.replan(
                    state=state,
                    context_updates=decision.updated_context,
                    specifications=self._registry.specifications(),
                )
                continue
            if decision.action == PlanReviewAction.ask_clarification:
                return await self._finish_with_mode(
                    mode=mode,
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
                    mode=mode,
                    state=state,
                    question=question,
                    context={**context, "error": decision.rationale},
                    presentation_mode="failure",
                    diagnostics={**diagnostics, "stop_reason": "abort"},
                )
            if decision.action == PlanReviewAction.finalize:
                return await self._finalize(
                    mode=mode,
                    state=state,
                    question=question,
                    context=context,
                    diagnostics={**diagnostics, "stop_reason": "finalize"},
                )

        return await self._finish_with_mode(
            mode=mode,
            state=state,
            question=question,
            context={**context, "error": "Meta-controller reached max iterations before finalizing."},
            presentation_mode="failure",
            diagnostics={**diagnostics, "stop_reason": "max_iterations"},
        )

    async def _finalize(
        self,
        *,
        mode: str,
        state: PlanExecutionState,
        question: str,
        context: dict[str, Any],
        diagnostics: dict[str, Any],
    ) -> MetaControllerRun:
        return await self._finish_with_mode(
            mode=mode,
            state=state,
            question=question,
            context=context,
            presentation_mode="final",
            diagnostics=diagnostics,
        )

    async def _finish_with_mode(
        self,
        *,
        mode: str,
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
        return self._build_run(mode=mode, state=state, final=final, diagnostics=diagnostics)

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
        result = await self._presentation_agent.execute(task)
        response = result.output.get("response")
        return response if isinstance(response, dict) else result.output

    @staticmethod
    def _build_run(
        *,
        mode: str,
        state: PlanExecutionState,
        final: dict[str, Any],
        diagnostics: dict[str, Any],
    ) -> MetaControllerRun:
        return MetaControllerRun(
            mode=mode,
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


__all__ = ["MetaControllerAgent", "MetaControllerRun"]
