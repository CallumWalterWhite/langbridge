"""Deterministic PEV verification for Langbridge AI."""

from __future__ import annotations

from pydantic import BaseModel, Field

from langbridge.ai.base import AgentResult, AgentResultStatus
from langbridge.ai.planner import PlanStep


class VerificationOutcome(BaseModel):
    passed: bool
    step_id: str
    agent_name: str
    message: str
    missing_output_keys: list[str] = Field(default_factory=list)


class AgentVerifier:
    """Verifies one executed plan step against deterministic contracts."""

    def verify(self, *, step: PlanStep, result: AgentResult) -> VerificationOutcome:
        if result.agent_name != step.agent_name:
            return VerificationOutcome(
                passed=False,
                step_id=step.step_id,
                agent_name=step.agent_name,
                message="Agent result came from a different agent.",
            )
        if result.status != AgentResultStatus.succeeded:
            return VerificationOutcome(
                passed=False,
                step_id=step.step_id,
                agent_name=step.agent_name,
                message=result.error or f"Agent returned status {result.status.value}.",
            )

        missing_keys = [
            key for key in step.expected_output.required_keys if key not in result.output
        ]
        if missing_keys:
            return VerificationOutcome(
                passed=False,
                step_id=step.step_id,
                agent_name=step.agent_name,
                message="Agent output missed required contract keys.",
                missing_output_keys=missing_keys,
            )

        return VerificationOutcome(
            passed=True,
            step_id=step.step_id,
            agent_name=step.agent_name,
            message="Step output passed deterministic verification.",
        )


__all__ = ["AgentVerifier", "VerificationOutcome"]
