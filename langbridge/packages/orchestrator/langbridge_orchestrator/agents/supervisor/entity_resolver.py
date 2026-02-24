from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider import LLMProvider

from .schemas import ClassifiedQuestion, ResolvedEntities


_TIME_PERIOD_PATTERNS = [
    re.compile(r"\b(20\d{2})\s*[-/]?\s*q([1-4])\b", re.IGNORECASE),
    re.compile(r"\bq([1-4])\s*[-/]?\s*(20\d{2})\b", re.IGNORECASE),
    re.compile(r"\b(20\d{2})\b", re.IGNORECASE),
]

_CURRENCY_PATTERN = re.compile(r"\b(usd|eur|gbp|cad|aud|jpy|chf|inr)\b|\$", re.IGNORECASE)
_REGION_PATTERN = re.compile(r"\bby\s+region\b|\bregion\s*[:=]\s*([a-z0-9\-\s]+)\b|\bin\s+([a-z\-\s]+?)\s+region\b", re.IGNORECASE)
_FUND_PATTERN = re.compile(r"\b([a-z0-9&.'\-]{2,}(?:\s+[a-z0-9&.'\-]{2,}){0,4})\s+fund\b|\bfund\s+([a-z0-9&.'\-]{2,}(?:\s+[a-z0-9&.'\-]{2,}){0,4})\b", re.IGNORECASE)

_INVALID_FUND_TOKENS = {
    "performance",
    "return",
    "returns",
    "region",
    "regions",
    "quarter",
    "q1",
    "q2",
    "q3",
    "q4",
    "2023",
    "2024",
    "2025",
    "2026",
}


class EntityResolver:
    """Entity + slot resolver used before clarification decisions."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._llm = llm
        self._logger = logger or logging.getLogger(__name__)

    async def resolve_async(
        self,
        question: str,
        *,
        classification: Optional[ClassifiedQuestion] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ResolvedEntities:
        heuristic = self._resolve_heuristically(question)
        llm_payload = await self._resolve_with_llm_async(question, classification=classification, context=context)
        if not llm_payload:
            return heuristic

        merged = heuristic.model_copy(deep=True)
        for slot in ("fund", "region", "time_period", "metric", "currency", "benchmark"):
            if getattr(merged, slot) and str(getattr(merged, slot)).strip():
                continue
            value = llm_payload.get(slot)
            if isinstance(value, str) and value.strip():
                setattr(merged, slot, value.strip())

        raw_entities = dict(merged.raw_entities)
        raw_llm = llm_payload.get("raw_entities")
        if isinstance(raw_llm, dict):
            raw_entities.update({str(k): v for k, v in raw_llm.items()})
        merged.raw_entities = raw_entities
        return merged

    def _resolve_heuristically(self, question: str) -> ResolvedEntities:
        text = str(question or "").strip()
        lowered = text.lower()

        fund = self._extract_fund(text)
        region = self._extract_region(text)
        time_period = self._extract_time_period(text)
        metric = self._extract_metric(lowered)
        currency = self._extract_currency(text)
        benchmark = self._extract_benchmark(lowered)

        return ResolvedEntities(
            fund=fund,
            region=region,
            time_period=time_period,
            metric=metric,
            currency=currency,
            benchmark=benchmark,
            raw_entities={"question": text},
        )

    @staticmethod
    def _extract_fund(text: str) -> Optional[str]:
        match = _FUND_PATTERN.search(text)
        if not match:
            return None
        candidate = (match.group(1) or match.group(2) or "").strip(" .,:;")
        if not candidate:
            return None
        lowered = candidate.lower()
        if lowered in _INVALID_FUND_TOKENS:
            return None
        if any(token in _INVALID_FUND_TOKENS for token in lowered.split()):
            if "fund" not in lowered:
                return None
        return candidate

    @staticmethod
    def _extract_region(text: str) -> Optional[str]:
        match = _REGION_PATTERN.search(text)
        if not match:
            return None
        if match.group(0):
            if "by region" in match.group(0).lower():
                return "by region"
        for idx in (1, 2):
            value = match.group(idx)
            if isinstance(value, str) and value.strip():
                return value.strip(" .,:;")
        return None

    @staticmethod
    def _extract_time_period(text: str) -> Optional[str]:
        for pattern in _TIME_PERIOD_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            if pattern is _TIME_PERIOD_PATTERNS[0]:
                return f"{match.group(1)} Q{match.group(2)}"
            if pattern is _TIME_PERIOD_PATTERNS[1]:
                return f"{match.group(2)} Q{match.group(1)}"
            if match.group(1):
                return str(match.group(1))
        lowered = text.lower()
        for token in ("ytd", "mtd", "qtd", "today", "yesterday", "last quarter", "this quarter"):
            if token in lowered:
                return token
        return None

    @staticmethod
    def _extract_metric(lowered_text: str) -> Optional[str]:
        if any(token in lowered_text for token in ("performance", "return", "returns", "alpha", "pnl")):
            return "performance"
        if any(token in lowered_text for token in ("aum", "assets under management")):
            return "aum"
        if any(token in lowered_text for token in ("revenue", "sales")):
            return "revenue"
        if any(token in lowered_text for token in ("cost", "expense", "spend")):
            return "cost"
        return None

    @staticmethod
    def _extract_currency(text: str) -> Optional[str]:
        match = _CURRENCY_PATTERN.search(text)
        if not match:
            return None
        token = match.group(0)
        if token == "$":
            return "USD"
        return token.upper()

    @staticmethod
    def _extract_benchmark(lowered_text: str) -> Optional[str]:
        if "benchmark" not in lowered_text:
            return None
        if any(token in lowered_text for token in ("without benchmark", "no benchmark", "exclude benchmark")):
            return "no"
        return "yes"

    async def _resolve_with_llm_async(
        self,
        question: str,
        *,
        classification: Optional[ClassifiedQuestion],
        context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(
            self._resolve_with_llm,
            question,
            classification,
            context,
        )

    def _resolve_with_llm(
        self,
        question: str,
        classification: Optional[ClassifiedQuestion],
        context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        prompt = self._build_prompt(question=question, classification=classification, context=context)
        try:
            response = self._llm.complete(prompt, temperature=0.0, max_tokens=320)
        except Exception as exc:  # pragma: no cover
            self._logger.warning("EntityResolver LLM call failed: %s", exc)
            return None

        return self._parse_json_payload(str(response))

    @staticmethod
    def _build_prompt(
        *,
        question: str,
        classification: Optional[ClassifiedQuestion],
        context: Optional[Dict[str, Any]],
    ) -> str:
        classification_payload = classification.model_dump() if classification else {}
        minimal_context: Dict[str, Any] = {}
        if isinstance(context, dict):
            for key in ("semantic_models", "retrieved_memories"):
                if key in context:
                    minimal_context[key] = context[key]

        return "\n".join(
            [
                "Extract canonical slots for an analytics request.",
                "Return ONLY JSON with keys: fund, region, time_period, metric, currency, benchmark, raw_entities.",
                "Use null for unknown slots.",
                f"Question: {question}",
                f"Classification JSON: {json.dumps(classification_payload, ensure_ascii=True, default=str)}",
                f"Context JSON: {json.dumps(minimal_context, ensure_ascii=True, default=str)}",
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
            payload = json.loads(response[start:end])
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload


__all__ = ["EntityResolver"]
