"""Specification-driven planner for Langbridge AI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

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
from langbridge.ai.routing import SpecificationRouter

if TYPE_CHECKING:  # pragma: no cover
    from langbridge.ai.execution import PlanExecutionState


class PlanStep(BaseModel):
    step_id: str
    agent_name: str
    task_kind: AgentTaskKind
    question: str
    input: dict[str, Any] = Field(default_factory=dict)
    expected_output: AgentIOContract = Field(default_factory=AgentIOContract)
    depends_on: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    route: str
    steps: list[PlanStep]
    rationale: str
    requires_pev: bool = True
    revision_count: int = 0


class PlannerAgent(BaseAgent):
    """Builds an execution plan from agent specifications."""

    def __init__(self, *, router: SpecificationRouter | None = None) -> None:
        self._router = router or SpecificationRouter()

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="planner",
            description="Builds specification-driven execution plans for the AI gateway.",
            task_kinds=[AgentTaskKind.orchestration],
            capabilities=["plan execution steps", "choose specialist agents", "prepare PEV contracts"],
            constraints=["Does not execute domain work directly."],
            routing=AgentRoutingSpec(keywords=["plan", "execute", "verify"], direct_threshold=99),
            can_execute_direct=False,
            output_contract=AgentIOContract(required_keys=["plan"]),
        )

    async def execute(self, task: AgentTask) -> AgentResult:
        raw_specifications = task.context.get("agent_specifications", [])
        specifications = [
            AgentSpecification.model_validate(item)
            if not isinstance(item, AgentSpecification)
            else item
            for item in raw_specifications
        ]
        plan = self.build_plan(
            question=task.question,
            context=task.context,
            specifications=specifications,
        )
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"plan": plan.model_dump(mode="json")},
            diagnostics={"step_count": len(plan.steps)},
        )

    def build_plan(
        self,
        *,
        question: str,
        context: dict[str, Any],
        specifications: list[AgentSpecification],
    ) -> ExecutionPlan:
        return self._build_plan(
            question=question,
            context=context,
            specifications=specifications,
            revision_count=0,
        )

    def replan(
        self,
        *,
        state: "PlanExecutionState",
        context_updates: dict[str, Any] | None = None,
        specifications: list[AgentSpecification],
    ) -> ExecutionPlan:
        context = {**state.context, **(context_updates or {})}
        failed_agents = {
            record.step.agent_name
            for record in state.failed_steps
            if record.step.agent_name != "presentation"
        }
        weak_agent = context.get("weak_result_agent")
        if isinstance(weak_agent, str) and weak_agent:
            failed_agents.add(weak_agent)
        failed_agent = context.get("failed_agent")
        if isinstance(failed_agent, str) and failed_agent:
            failed_agents.add(failed_agent)
        context["avoid_agents"] = sorted(failed_agents)
        return self._build_plan(
            question=state.original_question,
            context=context,
            specifications=specifications,
            revision_count=state.replan_count,
        )

    def _build_plan(
        self,
        *,
        question: str,
        context: dict[str, Any],
        specifications: list[AgentSpecification],
        revision_count: int,
    ) -> ExecutionPlan:
        runnable_specs = [
            specification
            for specification in specifications
            if AgentTaskKind.orchestration not in specification.task_kinds
            and AgentTaskKind.presentation not in specification.task_kinds
        ]
        avoid_agents = set(context.get("avoid_agents") or [])
        runnable_specs = [
            specification for specification in runnable_specs if specification.name not in avoid_agents
        ]
        ranked = [
            match
            for match in self._router.rank(question=question, specifications=runnable_specs)
            if match.score >= match.specification.routing.planner_threshold
        ]

        selected = [match.specification for match in ranked[:2]]
        analyst_spec = self._find_spec(runnable_specs, name="analyst", task_kind=AgentTaskKind.analyst)
        if context.get("verification_failure") and analyst_spec is not None:
            selected = [analyst_spec]

        if not selected and analyst_spec is not None:
            selected = [analyst_spec]

        steps = [
            self._build_step(
                index=index + 1,
                question=question,
                specification=specification,
                prior_steps=selected[:index],
                revision_count=revision_count,
            )
            for index, specification in enumerate(selected)
        ]
        return ExecutionPlan(
            route="planned",
            steps=steps,
            rationale="Planner selected agents from structured specifications.",
            requires_pev=True,
            revision_count=revision_count,
        )

    @staticmethod
    def _find_spec(
        specifications: list[AgentSpecification],
        *,
        name: str,
        task_kind: AgentTaskKind,
    ) -> AgentSpecification | None:
        return next(
            (
                specification
                for specification in specifications
                if specification.name == name or specification.supports(task_kind)
            ),
            None,
        )

    @staticmethod
    def _build_step(
        *,
        index: int,
        question: str,
        specification: AgentSpecification,
        prior_steps: list[AgentSpecification],
        revision_count: int = 0,
    ) -> PlanStep:
        input_payload: dict[str, Any] = {}
        if prior_steps:
            input_payload["uses_prior_step_outputs"] = True
        task_kind = specification.task_kinds[0]
        if specification.supports(AgentTaskKind.deep_research) and PlannerAgent._question_requests_research(question):
            task_kind = AgentTaskKind.deep_research
            input_payload["mode"] = "deep_research"
        prefix = f"r{revision_count}-" if revision_count else ""
        dependencies = [f"{prefix}step-{dependency}" for dependency in range(1, index)]
        return PlanStep(
            step_id=f"{prefix}step-{index}",
            agent_name=specification.name,
            task_kind=task_kind,
            question=question,
            input=input_payload,
            expected_output=specification.output_contract,
            depends_on=dependencies,
        )

    @staticmethod
    def _question_requests_research(question: str) -> bool:
        text = question.casefold()
        return any(
            cue in text
            for cue in (
                "search",
                "web",
                "latest",
                "current",
                "news",
                "source",
                "sources",
                "look up",
                "research",
                "investigate",
            )
        )


__all__ = ["ExecutionPlan", "PlannerAgent", "PlanStep"]
