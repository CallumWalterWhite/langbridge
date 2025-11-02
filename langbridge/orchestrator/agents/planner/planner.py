from __future__ import annotations

from typing import List

from .models import Plan, PlanStep, PlannerRequest, RouteDecision, RouteName
from .policies import PolicyNotes, check_policies
from .router import build_steps, choose_route


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


class PlanningAgent:
    """Stateless planner that returns executable plans for downstream orchestration."""

    def plan(self, request: PlannerRequest) -> Plan:
        policy_notes: PolicyNotes = check_policies(request)
        decision: RouteDecision = choose_route(request)
        steps: List[PlanStep] = build_steps(decision, request)
        user_summary = _summarize_plan(decision, steps, request)

        return Plan(
            route=decision.route.value,
            steps=steps,
            justification=decision.justification,
            user_summary=user_summary,
            assumptions=decision.assumptions,
            risks=policy_notes.risks,
        )


__all__ = ["PlanningAgent"]

