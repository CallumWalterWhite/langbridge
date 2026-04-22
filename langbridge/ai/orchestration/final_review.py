"""Semantic final review scaffold for Langbridge AI."""
import json
from enum import Enum
from typing import Any

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
from langbridge.ai.llm.base import LLMProvider
from langbridge.ai.orchestration.final_review_prompts import build_final_review_prompt


class FinalReviewAction(str, Enum):
    approve = "approve"
    revise_answer = "revise_answer"
    replan = "replan"
    ask_clarification = "ask_clarification"
    abort = "abort"


class FinalReviewReasonCode(str, Enum):
    grounded_complete = "grounded_complete"
    missing_caveat_or_framing = "missing_caveat_or_framing"
    insufficient_evidence_or_workflow = "insufficient_evidence_or_workflow"
    ambiguous_question = "ambiguous_question"
    unsafe_to_finalize = "unsafe_to_finalize"
    review_error = "review_error"


class FinalReviewDecision(BaseModel):
    action: FinalReviewAction
    reason_code: FinalReviewReasonCode
    rationale: str
    issues: list[str] = Field(default_factory=list)
    updated_context: dict[str, Any] = Field(default_factory=dict)
    clarification_question: str | None = None


class FinalReviewAgent(BaseAgent):
    """Reviews the current answer package before presentation."""

    def __init__(self, *, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="final-review",
            description="Reviews the current analytical answer package for grounding, completeness, and final-answer readiness.",
            task_kinds=[AgentTaskKind.orchestration],
            capabilities=["review final analytical answer", "detect unsupported claims", "request revise, replan, or clarification"],
            constraints=["Does not execute domain work directly.", "Does not format presentation output."],
            routing=AgentRoutingSpec(keywords=["review", "final review"], direct_threshold=99),
            can_execute_direct=False,
            output_contract=AgentIOContract(required_keys=["decision"]),
        )

    async def execute(self, task: AgentTask) -> AgentResult:
        answer_package = self._extract_mapping(task, "answer_package")
        if answer_package is None:
            return self.build_result(
                task=task,
                status=AgentResultStatus.failed,
                error="FinalReviewAgent requires answer_package in task context or input.",
            )

        decision = await self.review(
            question=task.question,
            answer_package=answer_package,
            evidence=self._extract_mapping(task, "evidence"),
            result=self._extract_mapping(task, "result"),
            research=self._extract_mapping(task, "research"),
            step_results=self._extract_sequence(task, "step_results"),
        )
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"decision": decision.model_dump(mode="json")},
            diagnostics={
                "action": decision.action.value,
                "reason_code": decision.reason_code.value,
                "issue_count": len(decision.issues),
            },
        )

    async def review(
        self,
        *,
        question: str,
        answer_package: dict[str, Any],
        evidence: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        research: dict[str, Any] | None = None,
        step_results: list[dict[str, Any]] | None = None,
    ) -> FinalReviewDecision:
        prompt = build_final_review_prompt(
            question=question,
            answer_package=answer_package,
            evidence=evidence,
            result=result,
            research=research,
            step_results=step_results,
            reason_codes=[item.value for item in FinalReviewReasonCode],
        )
        payload = self._parse_json_object(await self._llm.acomplete(prompt, temperature=0.0, max_tokens=700))
        self._ensure_reason_code(payload)
        return FinalReviewDecision.model_validate(payload)

    @staticmethod
    def _ensure_reason_code(payload: dict[str, Any]) -> None:
        if payload.get("reason_code"):
            return
        action = str(payload.get("action") or "").strip()
        inferred = {
            FinalReviewAction.approve.value: FinalReviewReasonCode.grounded_complete.value,
            FinalReviewAction.revise_answer.value: FinalReviewReasonCode.missing_caveat_or_framing.value,
            FinalReviewAction.replan.value: FinalReviewReasonCode.insufficient_evidence_or_workflow.value,
            FinalReviewAction.ask_clarification.value: FinalReviewReasonCode.ambiguous_question.value,
            FinalReviewAction.abort.value: FinalReviewReasonCode.unsafe_to_finalize.value,
        }.get(action)
        if inferred:
            payload["reason_code"] = inferred

    @staticmethod
    def _extract_mapping(task: AgentTask, key: str) -> dict[str, Any] | None:
        for candidate in (task.context.get(key), task.input.get(key)):
            if isinstance(candidate, dict):
                return candidate
        return None

    @staticmethod
    def _extract_sequence(task: AgentTask, key: str) -> list[dict[str, Any]] | None:
        for candidate in (task.context.get(key), task.input.get(key)):
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        return None

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Final review LLM response did not contain a JSON object.")
        parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("Final review LLM response JSON must be an object.")
        return parsed


__all__ = ["FinalReviewAction", "FinalReviewAgent", "FinalReviewDecision", "FinalReviewReasonCode"]
