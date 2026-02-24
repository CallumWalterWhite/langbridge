from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from langbridge.packages.orchestrator.langbridge_orchestrator.agents.planner.models import RouteName
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
    """LLM-native classifier with no heuristic fallback routing."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._llm = llm
        self._logger = logger or logging.getLogger(__name__)

    async def classify_async(self, question: str, context: Optional[Dict[str, Any]] = None) -> ClassifiedQuestion:
        llm_result = await self._classify_with_llm_async(question, context=context)
        if llm_result is None:
            raise RuntimeError("QuestionClassifier LLM returned an invalid payload; fallback routing is disabled.")
        return llm_result

    async def _classify_with_llm_async(
        self,
        question: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ClassifiedQuestion]:
        return await asyncio.to_thread(self._classify_with_llm, question, context)

    def _classify_with_llm(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ClassifiedQuestion]:
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
        required_context = payload.get("required_context") or payload.get("missing_context") or []
        if isinstance(required_context, str):
            required_context = [required_context]
        if not isinstance(required_context, list):
            required_context = []
        required_context_clean = [str(item).strip() for item in required_context if str(item).strip()]
        clarifying_question = payload.get("clarifying_question")
        if isinstance(clarifying_question, str):
            clarifying_question = clarifying_question.strip() or None
        else:
            clarifying_question = None
        if requires_clarification and not clarifying_question:
            if required_context_clean:
                clarifying_question = "Please clarify: " + ", ".join(required_context_clean[:3]) + "."
            else:
                clarifying_question = "What additional context should I use before I proceed?"

        return ClassifiedQuestion(
            intent=intent,
            route_hint=route_hint or None,
            confidence=confidence_value,
            requires_clarification=requires_clarification,
            clarifying_question=clarifying_question,
            required_context=required_context_clean,
            extracted_entities={str(k): str(v) for k, v in extracted_entities.items() if str(v).strip()},
            rationale=str(rationale).strip() if isinstance(rationale, str) and rationale.strip() else None,
        )

    @staticmethod
    def _build_prompt(question: str, context: Optional[Dict[str, Any]]) -> str:
        context_payload: Dict[str, Any] = {}
        if isinstance(context, dict):
            for key in (
                "available_agents",
                "available_tools",
                "tool_capabilities",
                "semantic_models_count",
                "semantic_models",
                "connector_names",
                "routing",
                "resolved_entities",
                "retrieved_memories",
                "short_term_context",
                "conversation_context",
            ):
                if key in context:
                    context_payload[key] = context[key]

        return "\n".join(
            [
                "You are a supervisor router for an enterprise analytics assistant.",
                "Classify the question and return ONLY JSON.",
                "JSON keys: intent, route_hint, confidence, requires_clarification, clarifying_question, required_context, extracted_entities, rationale.",
                "intent one of: analytical, web_search, research, clarification, chat.",
                "route_hint one of: SimpleAnalyst, AnalystThenVisual, WebSearch, DeepResearch, Clarify.",
                "required_context must list only truly blocking missing items.",
                "If requires_clarification=true, provide one targeted clarifying_question and set route_hint='Clarify'.",
                "Do not ask for fund/id unless the user explicitly asks about fund analytics.",
                "Use available context (memories, short-term context, tool availability) before deciding clarification.",
                "No heuristic assumptions: decide directly from the prompt and context.",
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
