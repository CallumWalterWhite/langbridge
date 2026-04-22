"""Final response presentation agent for Langbridge AI."""
import json
from typing import Any

from langbridge.ai.base import (
    AgentIOContract,
    AgentResult,
    AgentResultStatus,
    AgentRoutingSpec,
    AgentSpecification,
    AgentTask,
    AgentTaskKind,
    AgentToolSpecification,
    BaseAgent,
)
from langbridge.ai.events import AIEventEmitter, AIEventSource
from langbridge.ai.llm.base import LLMProvider
from langbridge.ai.agents.presentation.prompts import build_presentation_prompt
from langbridge.ai.tools.charting import ChartSpec, ChartingTool


class PresentationAgent(AIEventSource, BaseAgent):
    """Composes final user-facing responses from verified outputs."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        charting_tool: ChartingTool | None = None,
        event_emitter: AIEventEmitter | None = None,
    ) -> None:
        super().__init__(event_emitter=event_emitter)
        self._llm = llm_provider
        self._charting_tool = charting_tool

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="presentation",
            description="Composes final user-facing responses from verified agent outputs.",
            task_kinds=[AgentTaskKind.presentation],
            capabilities=["compose final response", "summarize tables", "render research", "request charts"],
            constraints=["Does not perform source execution directly."],
            routing=AgentRoutingSpec(keywords=["present", "response", "chart"], direct_threshold=99),
            can_execute_direct=False,
            output_contract=AgentIOContract(required_keys=["response"]),
            tools=[
                AgentToolSpecification(
                    name="charting",
                    description="Builds chart specifications from tabular result data when configured.",
                    output_contract=AgentIOContract(required_keys=["chart_type"]),
                )
            ],
        )

    async def execute(self, task: AgentTask) -> AgentResult:
        response = await self.compose(
            question=task.question,
            context=task.context,
            mode=str(task.input.get("mode") or "final"),
        )
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"response": response},
        )

    async def compose(self, *, question: str, context: dict[str, Any], mode: str = "final") -> dict[str, Any]:
        await self._emit_ai_event(
            event_type="PresentationCompositionStarted",
            message="Composing final answer.",
            source="presentation",
            details={"mode": mode},
        )
        step_results = [item for item in context.get("step_results", []) if isinstance(item, dict)]
        data_payload = self._find_data_payload(step_results)
        analysis_payload = self._find_key_payload(step_results, "analysis")
        research_payload = self._find_key_payload(step_results, "synthesis")
        answer_payload = self._find_key_payload(step_results, "answer")
        visualization = await self._maybe_chart(question=question, data_payload=data_payload)
        prompt = build_presentation_prompt(
            question=question,
            mode=mode,
            context=context,
            data_payload=data_payload,
            analysis_payload=analysis_payload,
            research_payload=research_payload,
            answer_payload=answer_payload,
            visualization=visualization,
        )
        parsed = self._parse_json_object(
            await self._llm.acomplete(
                prompt,
                temperature=0.0,
                max_tokens=1600,
            )
        )
        parsed_result = parsed.get("result")
        parsed_research = parsed.get("research")
        response = {
            "summary": str(parsed.get("summary") or ""),
            "result": parsed_result if isinstance(parsed_result, dict) and parsed_result else data_payload or {},
            "visualization": parsed.get("visualization")
            if isinstance(parsed.get("visualization"), dict)
            else (visualization.model_dump(mode="json") if visualization else None),
            "research": (
                parsed_research
                if isinstance(parsed_research, dict) and parsed_research
                else research_payload or {}
            ),
            "answer": self._resolve_answer(
                parsed=parsed,
                mode=mode,
                context=context,
                summary=str(parsed.get("summary") or ""),
                analysis_payload=analysis_payload,
                research_payload=research_payload,
                answer_payload=answer_payload,
            ),
            "diagnostics": parsed.get("diagnostics") if isinstance(parsed.get("diagnostics"), dict) else {"mode": mode},
        }
        if not response["summary"]:
            raise ValueError("Presentation LLM response missing summary.")
        await self._emit_ai_event(
            event_type="PresentationCompositionCompleted",
            message="Answer composed.",
            source="presentation",
            details={"has_visualization": isinstance(response.get("visualization"), dict)},
        )
        return response

    async def _maybe_chart(
        self,
        *,
        question: str,
        data_payload: dict[str, Any] | None,
    ) -> ChartSpec | None:
        if self._charting_tool is None or not data_payload or not self._question_requests_chart(question):
            return None
        return await self._charting_tool.build_chart(data_payload, question=question)

    @staticmethod
    def _find_data_payload(step_results: list[dict[str, Any]]) -> dict[str, Any] | None:
        for item in reversed(step_results):
            output = item.get("output")
            if not isinstance(output, dict):
                continue
            result = output.get("result")
            if isinstance(result, dict) and {"columns", "rows"}.issubset(result):
                return result
            artifact = item.get("artifacts")
            if isinstance(artifact, dict):
                tabular = artifact.get("tabular")
                if isinstance(tabular, dict) and {"columns", "rows"}.issubset(tabular):
                    return tabular
        return None

    @staticmethod
    def _find_key_payload(step_results: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
        for item in reversed(step_results):
            output = item.get("output")
            if isinstance(output, dict) and key in output:
                return output
        return None

    @staticmethod
    def _resolve_answer(
        *,
        parsed: dict[str, Any],
        mode: str,
        context: dict[str, Any],
        summary: str,
        analysis_payload: dict[str, Any] | None,
        research_payload: dict[str, Any] | None,
        answer_payload: dict[str, Any] | None,
    ) -> Any:
        if parsed.get("answer") is not None:
            return parsed.get("answer")
        if mode == "clarification":
            return context.get("clarification_question") or summary or None
        if mode == "failure":
            return context.get("error") or summary or None
        for payload, key in (
            (answer_payload, "answer"),
            (analysis_payload, "analysis"),
            (research_payload, "synthesis"),
        ):
            if not isinstance(payload, dict):
                continue
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return summary or None

    @staticmethod
    def _question_requests_chart(question: str) -> bool:
        text = question.casefold()
        return any(token in text for token in ("chart", "graph", "plot", "visual", "bar", "line"))

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Presentation LLM response did not contain a JSON object.")
        parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("Presentation LLM response JSON must be an object.")
        return parsed


__all__ = ["PresentationAgent"]
