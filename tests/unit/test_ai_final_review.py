import asyncio

from langbridge.ai import AgentResultStatus, AgentTask, AgentTaskKind
from langbridge.ai.orchestration.final_review import (
    FinalReviewAction,
    FinalReviewAgent,
    FinalReviewDecision,
    FinalReviewReasonCode,
)
from langbridge.ai.orchestration.final_review_prompts import build_final_review_prompt


def _run(coro):
    return asyncio.run(coro)


class _FakeLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        if "Ambiguous revenue request" in prompt:
            return (
                '{"action":"ask_clarification","reason_code":"ambiguous_question",'
                '"rationale":"The answer package does not resolve which revenue metric to use.",'
                '"issues":["Metric scope is ambiguous."],"updated_context":{"needs_metric_scope":true},'
                '"clarification_question":"Which revenue metric should I use?"}'
            )
        return (
            '{"action":"approve","reason_code":"grounded_complete",'
            '"rationale":"The answer is grounded in the supplied evidence.",'
            '"issues":[],"updated_context":{},"clarification_question":null}'
        )

    async def create_embeddings(self, texts, embedding_model=None):
        return [[1.0] for _ in texts]


def test_build_final_review_prompt_includes_question_and_answer_package() -> None:
    prompt = build_final_review_prompt(
        question="What changed in revenue by region?",
        answer_package={"answer": "US revenue increased 12% quarter over quarter."},
        evidence={"governed": {"datasets": ["orders"]}},
        result={"columns": ["region", "revenue"], "rows": [["US", 1200]]},
        research={"sources": [{"url": "https://example.test/source"}]},
    )

    assert "What changed in revenue by region?" in prompt
    assert '"answer": "US revenue increased 12% quarter over quarter."' in prompt
    assert '"reason_code":"' in prompt
    assert '"datasets": [' in prompt
    assert '"sources": [' in prompt


def test_final_review_agent_returns_structured_approval_decision() -> None:
    agent = FinalReviewAgent(llm_provider=_FakeLLMProvider())

    result = _run(
        agent.execute(
            AgentTask(
                task_id="final-review",
                task_kind=AgentTaskKind.orchestration,
                question="What changed in revenue by region?",
                context={
                    "answer_package": {
                        "summary": "US revenue increased quarter over quarter.",
                        "answer": "US revenue increased 12% quarter over quarter.",
                    },
                    "evidence": {
                        "governed": {"datasets": ["orders"]},
                        "sufficiency": "sufficient",
                    },
                    "result": {
                        "columns": ["region", "revenue"],
                        "rows": [["US", 1200]],
                    },
                    "research": {"sources": []},
                },
            )
        )
    )

    assert result.status == AgentResultStatus.succeeded
    assert result.diagnostics["action"] == "approve"
    assert result.diagnostics["reason_code"] == FinalReviewReasonCode.grounded_complete.value
    decision = FinalReviewDecision.model_validate(result.output["decision"])
    assert decision.action == FinalReviewAction.approve
    assert decision.reason_code == FinalReviewReasonCode.grounded_complete
    assert decision.issues == []


def test_final_review_agent_parses_clarification_decision() -> None:
    agent = FinalReviewAgent(llm_provider=_FakeLLMProvider())

    result = _run(
        agent.execute(
            AgentTask(
                task_id="final-review",
                task_kind=AgentTaskKind.orchestration,
                question="Ambiguous revenue request",
                context={
                    "answer_package": {"answer": "Revenue increased."},
                    "evidence": {"governed": {"datasets": ["orders"]}},
                },
            )
        )
    )

    decision = FinalReviewDecision.model_validate(result.output["decision"])

    assert decision.action == FinalReviewAction.ask_clarification
    assert decision.reason_code == FinalReviewReasonCode.ambiguous_question
    assert decision.updated_context["needs_metric_scope"] is True
    assert decision.clarification_question == "Which revenue metric should I use?"


def test_final_review_agent_requires_answer_package() -> None:
    agent = FinalReviewAgent(llm_provider=_FakeLLMProvider())

    result = _run(
        agent.execute(
            AgentTask(
                task_id="final-review",
                task_kind=AgentTaskKind.orchestration,
                question="What changed in revenue by region?",
                context={"evidence": {"governed": {"datasets": ["orders"]}}},
            )
        )
    )

    assert result.status == AgentResultStatus.failed
    assert result.error == "FinalReviewAgent requires answer_package in task context or input."
