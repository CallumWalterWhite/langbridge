"""LLM-backed chart specification tool."""

import json
from typing import Any

from pydantic import BaseModel, Field

from langbridge.ai.events import AIEventEmitter, AIEventSource
from langbridge.ai.llm.base import LLMProvider


class ChartSpec(BaseModel):
    chart_type: str
    title: str
    x: str | None = None
    y: str | None = None
    series: str | None = None
    encoding: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None


class ChartingTool(AIEventSource):
    """Builds chart specifications through an LLM provider."""

    def __init__(self, *, llm_provider: LLMProvider, event_emitter: AIEventEmitter | None = None) -> None:
        super().__init__(event_emitter=event_emitter)
        self._llm = llm_provider

    async def build_chart(
        self,
        data: dict[str, Any],
        *,
        question: str,
        title: str | None = None,
        user_intent: str | None = None,
    ) -> ChartSpec | None:
        columns = data.get("columns")
        rows = data.get("rows")
        if not isinstance(columns, list) or not isinstance(rows, list) or not columns or not rows:
            return None
        await self._emit_ai_event(
            event_type="ChartingStarted",
            message="Building chart specification.",
            source="charting",
            details={"column_count": len(columns), "row_count": len(rows)},
        )
        prompt = self._build_prompt(
            columns=[str(column) for column in columns],
            rows=rows[:20],
            question=question,
            title=title,
            user_intent=user_intent,
        )
        raw = await self._llm.acomplete(prompt, temperature=0.0, max_tokens=700)
        chart = ChartSpec.model_validate(self._parse_json_object(raw))
        await self._emit_ai_event(
            event_type="ChartingCompleted",
            message=f"Chart specification ready: {chart.chart_type}.",
            source="charting",
            details={"chart_type": chart.chart_type},
        )
        return chart

    @staticmethod
    def _build_prompt(
        *,
        columns: list[str],
        rows: list[Any],
        question: str,
        title: str | None,
        user_intent: str | None,
    ) -> str:
        return (
            "Create a chart specification for verified tabular data.\n"
            "Return STRICT JSON only.\n"
            "Schema: {\"chart_type\":\"bar|line|area|scatter|pie|table\","
            "\"title\":\"...\",\"x\":\"column\",\"y\":\"column\",\"series\":\"column|null\","
            "\"encoding\":{},\"rationale\":\"...\"}\n"
            "Use only provided column names. Return table if chart is not appropriate.\n"
            f"Question: {question}\n"
            f"Title: {title or ''}\n"
            f"User intent: {user_intent or ''}\n"
            f"Columns: {json.dumps(columns)}\n"
            f"Rows sample: {json.dumps(rows, default=str)}\n"
        )

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Charting LLM response did not contain a JSON object.")
        return json.loads(text[start : end + 1])


__all__ = ["ChartSpec", "ChartingTool"]
