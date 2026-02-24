from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from langbridge.packages.orchestrator.langbridge_orchestrator.agents.planner.models import RouteName
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.planner.router import _extract_signals
from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider import LLMProvider

from .schemas import ClassifiedQuestion


_ALLOWED_ROUTE_HINTS = {
    RouteName.SIMPLE_ANALYST.value,
    RouteName.ANALYST_THEN_VISUAL.value,
    RouteName.WEB_SEARCH.value,
    RouteName.DEEP_RESEARCH.value,
    RouteName.CLARIFY.value,
}


class QuestionClassifier:
    """LLM-first classifier with deterministic fallbacks."""

    def __init__(
        self,
        *,
        llm: Optional[LLMProvider] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._llm = llm
        self._logger = logger or logging.getLogger(__name__)

    async def classify_async(self, question: str, context: Optional[Dict[str, Any]] = None) -> ClassifiedQuestion:
        llm_result = await self._classify_with_llm_async(question, context=context)
        if llm_result is not None:
            return llm_result
        return self._classify_with_rules(question)

    def _classify_with_rules(self, question: str) -> ClassifiedQuestion:
        text = str(question or "").strip()
        lowered = text.lower()
        signals = _extract_signals(text)

        is_visual = bool(re.search(r"\b(chart|graph|plot|dashboard|visualize|visualise)\b", lowered))
        is_web = signals.has_web_search_signals
        is_research = signals.has_research_signals

        analytical_cues = (
            signals.has_sql_signals
            or "performance" in lowered
            or "return" in lowered
            or "pnl" in lowered
            or "breakdown" in lowered
            or bool(re.search(r"\b(q[1-4]|20\d{2}|month|quarter|year|ytd|mtd)\b", lowered))
            or " by " in f" {lowered} "
        )

        if is_web:
            return ClassifiedQuestion(
                intent="web_search",
                route_hint=RouteName.WEB_SEARCH.value,
                confidence=0.8,
                requires_clarification=False,
                rationale="Question explicitly requested web/internet lookup.",
            )

        if is_research and not analytical_cues:
            return ClassifiedQuestion(
                intent="research",
                route_hint=RouteName.DEEP_RESEARCH.value,
                confidence=0.75,
                requires_clarification=False,
                rationale="Question is dominated by document/research intent.",
            )

        if analytical_cues and is_visual:
            return ClassifiedQuestion(
                intent="analytical",
                route_hint=RouteName.ANALYST_THEN_VISUAL.value,
                confidence=0.78,
                requires_clarification=False,
                rationale="Analytical query with explicit visualization cue.",
            )

        if analytical_cues:
            return ClassifiedQuestion(
                intent="analytical",
                route_hint=RouteName.SIMPLE_ANALYST.value,
                confidence=0.74,
                requires_clarification=False,
                rationale="Analytical query detected from metric/entity/time cues.",
            )

        if signals.requires_clarification:
            return ClassifiedQuestion(
                intent="clarification",
                route_hint=RouteName.CLARIFY.value,
                confidence=0.7,
                requires_clarification=True,
                rationale="Query appears underspecified.",
            )

        return ClassifiedQuestion(
            intent="analytical",
            route_hint=RouteName.SIMPLE_ANALYST.value,
            confidence=0.52,
            requires_clarification=False,
            rationale="Fallback route selected.",
        )

    async def _classify_with_llm_async(
        self,
        question: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ClassifiedQuestion]:
        if not self._llm:
            return None
        return await asyncio.to_thread(self._classify_with_llm, question, context)

    def _classify_with_llm(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ClassifiedQuestion]:
        if not self._llm:
            return None

        prompt = self._build_prompt(question=question, context=context)
        try:
            response = self._llm.complete(prompt, temperature=0.0, max_tokens=320)
        except Exception as exc:  # pragma: no cover
            self._logger.warning("QuestionClassifier LLM call failed: %s", exc)
            return None

        payload = self._parse_json_payload(str(response))
        if not payload:
            return None

        route_hint = str(payload.get("route_hint") or payload.get("route") or "").strip()
        if route_hint and route_hint not in _ALLOWED_ROUTE_HINTS:
            route_hint = ""

        confidence = payload.get("confidence")
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.0
        confidence_value = max(0.0, min(1.0, confidence_value))

        requires_clarification = bool(payload.get("requires_clarification"))
        rationale = payload.get("rationale")
        intent = str(payload.get("intent") or "analytical").strip() or "analytical"

        extracted_entities = payload.get("extracted_entities") or payload.get("entities") or {}
        if not isinstance(extracted_entities, dict):
            extracted_entities = {}

        return ClassifiedQuestion(
            intent=intent,
            route_hint=route_hint or None,
            confidence=confidence_value,
            requires_clarification=requires_clarification,
            extracted_entities={str(k): str(v) for k, v in extracted_entities.items() if str(v).strip()},
            rationale=str(rationale).strip() if isinstance(rationale, str) and rationale.strip() else None,
        )

    @staticmethod
    def _build_prompt(question: str, context: Optional[Dict[str, Any]]) -> str:
        context_payload: Dict[str, Any] = {}
        if isinstance(context, dict):
            for key in (
                "available_agents",
                "semantic_models_count",
                "resolved_entities",
                "retrieved_memories",
                "short_term_context",
            ):
                if key in context:
                    context_payload[key] = context[key]

        return "\n".join(
            [
                "You are a supervisor router for an enterprise analytics assistant.",
                "Classify the question and return ONLY JSON.",
                "JSON keys: intent, route_hint, confidence, requires_clarification, extracted_entities, rationale.",
                "intent one of: analytical, web_search, research, clarification, chat.",
                "route_hint one of: SimpleAnalyst, AnalystThenVisual, WebSearch, DeepResearch, Clarify.",
                f"Question: {question}",
                f"Context JSON: {json.dumps(context_payload, ensure_ascii=True, default=str)}",
            ]
        )

    @staticmethod
    def _parse_json_payload(response: str) -> Optional[Dict[str, Any]]:
        start = response.find("{")
        if start == -1:
            return None
        depth = 0
        end = -1
        for index in range(start, len(response)):
            char = response[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end == -1:
            return None
        try:
            parsed = json.loads(response[start:end])
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed


__all__ = ["QuestionClassifier"]
