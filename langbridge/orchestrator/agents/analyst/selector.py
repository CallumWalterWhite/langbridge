"""
Semantic-aware selection strategy for SQL analyst tools using an LLM router.
"""

import json
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from orchestrator.llm.provider import LLMProvider
from orchestrator.tools.sql_analyst.interfaces import AnalystQueryRequest
from orchestrator.tools.sql_analyst.tool import SqlAnalystTool

TOKEN_RE = re.compile(r"\b\w+\b")


class ToolSelectionError(RuntimeError):
    """Raised when the agent cannot determine an appropriate tool."""


@dataclass(frozen=True)
class ToolCandidate:
    tool: SqlAnalystTool
    score: float
    priority: int
    order: int


class SemanticToolSelector:
    """
    Select a SqlAnalystTool for a natural language query using an LLM,
    with a keyword-based fallback.
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: Sequence[SqlAnalystTool],
    ) -> None:
        if not tools:
            raise ValueError("SemanticToolSelector requires at least one SqlAnalystTool instance.")

        self._llm = llm
        self._tools = list(tools)

        # Pre-compute lightweight metadata for prompt + fallback scoring
        self._keywords = {
            tool: self._extract_keywords(tool.semantic_model)
            for tool in self._tools
        }
        self._tool_descriptions = {
            str(idx): self._build_model_description(tool, idx)
            for idx, tool in enumerate(self._tools)
        }
        self._tool_by_id = {
            desc["id"]: tool for tool, desc in zip(self._tools, self._tool_descriptions.values())
        }

    def select(self, request: AnalystQueryRequest) -> SqlAnalystTool:
        """
        Use the LLM to pick the most appropriate tool.

        If the LLM fails, is unavailable, or returns an invalid response,
        fall back to deterministic keyword-based scoring.
        """
        if not self._tools:
            raise ToolSelectionError("No SqlAnalystTool instances are available for selection.")
        if len(self._tools) == 1:
            return self._tools[0]
        try:
            llm_choice = self._select_with_llm(request)
            if llm_choice is not None:
                return llm_choice
        except Exception:
            # Any LLM failure should degrade gracefully to the old behaviour
            pass

        return self._fallback_select(request)

    def _select_with_llm(self, request: AnalystQueryRequest) -> SqlAnalystTool | None:
        prompt = self._build_llm_prompt(request)
        response_text = self._llm.complete(prompt=prompt, temperature=0.0)

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            return None

        tool_id = str(data.get("tool_id") or data.get("tool") or "").strip()
        if not tool_id:
            return None

        tool = self._tool_by_id.get(tool_id)
        return tool

    def _build_llm_prompt(self, request: AnalystQueryRequest) -> str:
        """
        Build a single-string prompt instructing the LLM to choose exactly one tool.

        The LLM is asked to return a minimal JSON payload:
        {
          "tool_id": "<id>",
          "reason": "<short explanation>"
        }
        """
        question = request.question.strip()
        filters = request.filters or {}

        tools_block = json.dumps(
            list(self._tool_descriptions.values()),
            indent=2,
            default=str,
        )

        return f"""
You are a routing assistant for a SQL analyst system.

You are given:
- A natural language question from an analyst.
- Optional filters (dimensions/constraints).
- A list of semantic models, each associated with a tool that can answer queries.

Your job:
1. Carefully read the question and filters.
2. Choose the SINGLE most appropriate semantic model/tool that should be used
   to answer this question.
3. If multiple tools could work, choose the one with the highest `priority` value.
4. Only choose tools that reasonably match the domain of the question.
5. If you're unsure, still pick the best candidate based on the descriptions.

Return your answer as STRICT JSON with the following shape and nothing else:
{{
  "tool_id": "<ID of the chosen tool>",
  "reason": "<very short explanation>"
}}

Question:
{question}

Filters (if any):
{json.dumps(filters, indent=2)}

Available tools and their semantic models:
{tools_block}
""".strip()

    def _build_model_description(self, tool: SqlAnalystTool, idx: int) -> dict:
        """
        Build a structured description of the tool and its semantic model
        to feed into the LLM.
        """
        semantic_model = getattr(tool, "semantic_model", None)
        model_name = getattr(semantic_model, "name", None) or getattr(tool, "name", None) or f"tool_{idx}"
        description = getattr(semantic_model, "description", None) or ""
        tags = list(getattr(semantic_model, "tags", []) or [])
        keywords = sorted(self._keywords.get(tool, []))

        entities = []
        metrics = []
        dimensions = []

        if semantic_model is not None:
            # entities
            for entity_name, entity in (getattr(semantic_model, "entities", {}) or {}).items():
                entity_desc = {
                    "name": str(entity_name),
                    "aliases": [],
                    "synonyms": [],
                    "columns": [],
                }
                if isinstance(entity, dict):
                    entity_desc["aliases"] = list(entity.get("aliases", []) or [])
                    entity_desc["synonyms"] = list(entity.get("synonyms", []) or [])
                    entity_desc["columns"] = list((entity.get("columns") or {}).keys())
                entities.append(entity_desc)

            # metrics
            for metric_name, metric in (getattr(semantic_model, "metrics", {}) or {}).items():
                metric_desc = {"name": str(metric_name), "synonyms": []}
                if isinstance(metric, dict):
                    metric_desc["synonyms"] = list(metric.get("synonyms", []) or [])
                metrics.append(metric_desc)

            # dimensions
            for dim_name, dim in (getattr(semantic_model, "dimensions", {}) or {}).items():
                dim_desc = {"name": str(dim_name), "synonyms": []}
                if isinstance(dim, dict):
                    dim_desc["synonyms"] = list(dim.get("synonyms", []) or [])
                dimensions.append(dim_desc)

        return {
            "id": str(idx),
            "priority": getattr(tool, "priority", 0),
            "name": str(model_name),
            "description": str(description),
            "tags": tags,
            "keywords": keywords,
            "entities": entities,
            "metrics": metrics,
            "dimensions": dimensions,
        }

    # -------------------------------------------------------------------------
    # Fallback: deterministic keyword-based selection (previous behaviour)
    # -------------------------------------------------------------------------
    def _fallback_select(self, request: AnalystQueryRequest) -> SqlAnalystTool:
        tokens = self._tokenize(request.question)
        if request.filters:
            tokens.update(self._tokenize(" ".join(request.filters.keys())))

        candidates: list[ToolCandidate] = []
        for idx, tool in enumerate(self._tools):
            keywords = self._keywords[tool]
            score = self._score(tokens, keywords)
            candidates.append(
                ToolCandidate(
                    tool=tool,
                    score=score,
                    priority=getattr(tool, "priority", 0),
                    order=idx,
                )
            )

        best = max(
            candidates,
            key=lambda candidate: (candidate.score, candidate.priority, -candidate.order),
        )

        if best.score == 0:
            # If no clear match, pick highest priority / first tool to ensure progress.
            fallback = max(
                candidates,
                key=lambda candidate: (candidate.priority, -candidate.order),
            )
            return fallback.tool

        return best.tool

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token.lower() for token in TOKEN_RE.findall(text or "")}

    @staticmethod
    def _score(tokens: set[str], keywords: set[str]) -> float:
        if not keywords:
            return 0.0
        matches = tokens.intersection(keywords)
        return float(len(matches)) / float(len(keywords))

    @staticmethod
    def _extract_keywords(semantic_model) -> set[str]:
        keywords: set[str] = set()

        def _consume_values(values: Iterable[str]) -> None:
            for value in values:
                if not value:
                    continue
                keywords.add(str(value).lower())

        def _collect_from_model(model) -> None:
            name = getattr(model, "name", None)
            if name:
                keywords.add(str(name).lower())
            for tag in getattr(model, "tags", []) or []:
                _consume_values([tag])

            entities = getattr(model, "entities", {}) or {}
            for entity_name, entity in entities.items():
                keywords.add(str(entity_name).lower())
                if isinstance(entity, dict):
                    _consume_values(entity.get("aliases", []) or [])
                    _consume_values(entity.get("synonyms", []) or [])
                    for column_name, column_meta in (entity.get("columns") or {}).items():
                        keywords.add(str(column_name).lower())
                        if isinstance(column_meta, dict):
                            _consume_values(column_meta.get("synonyms", []) or [])

            for metric_name, metric in (getattr(model, "metrics", {}) or {}).items():
                keywords.add(str(metric_name).lower())
                if isinstance(metric, dict):
                    _consume_values(metric.get("synonyms", []) or [])

            for dimension_name, dimension in (getattr(model, "dimensions", {}) or {}).items():
                keywords.add(str(dimension_name).lower())
                if isinstance(dimension, dict):
                    _consume_values(dimension.get("synonyms", []) or [])

        if hasattr(semantic_model, "semantic_models"):
            for model in getattr(semantic_model, "semantic_models") or []:
                _collect_from_model(model)
            relationships = getattr(semantic_model, "relationships", None) or []
            for rel in relationships:
                _consume_values([rel.get("name"), rel.get("from"), rel.get("to")])
        else:
            _collect_from_model(semantic_model)

        return keywords


__all__ = ["SemanticToolSelector", "ToolSelectionError"]
