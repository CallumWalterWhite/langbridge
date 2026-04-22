import asyncio

from langbridge.ai.agents.presentation import PresentationAgent


def _run(coro):
    return asyncio.run(coro)


class _PromptCheckingLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        assert "Compose the final Langbridge response" in prompt
        assert "Decide the answer depth from the question and evidence" in prompt
        assert "Use a detailed answer when the user asks for explanation, evidence, comparisons, drivers, caveats, or source-backed reasoning." in prompt
        assert '"analysis": "Detailed governed answer with evidence."' in prompt
        assert kwargs["max_tokens"] == 1600
        return (
            '{"summary":"Detailed answer ready.",'
            '"result":{},"visualization":null,"research":{},"diagnostics":{"mode":"final"}}'
        )


def test_presentation_falls_back_to_detailed_analysis_when_answer_missing() -> None:
    agent = PresentationAgent(llm_provider=_PromptCheckingLLMProvider())

    response = _run(
        agent.compose(
            question="Explain the detailed evidence for the order trend",
            context={
                "step_results": [
                    {
                        "agent_name": "analyst",
                        "output": {
                            "analysis": "Detailed governed answer with evidence.",
                            "result": {
                                "columns": ["month", "orders"],
                                "rows": [["2026-01-01", 12]],
                            },
                            "evidence": {
                                "governed": {
                                    "attempted": True,
                                    "answered_question": True,
                                }
                            },
                        },
                    }
                ]
            },
        )
    )

    assert response["summary"] == "Detailed answer ready."
    assert response["answer"] == "Detailed governed answer with evidence."
    assert response["result"]["rows"] == [["2026-01-01", 12]]
