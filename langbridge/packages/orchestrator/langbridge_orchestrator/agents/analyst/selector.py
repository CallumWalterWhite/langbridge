"""
Semantic-aware selection strategy for SQL analyst tools using an LLM router.
"""

import json
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider import LLMProvider
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.sql_analyst.interfaces import AnalystQueryRequest
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.sql_analyst.tool import SqlAnalystTool

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

        tables = []
        metrics = []
        dimensions = []
        measures = []

        if semantic_model is not None:
            for table_key, table in getattr(semantic_model, "tables", {}).items():
                table_desc = {
                    "name": str(table_key),
                    "schema": str(getattr(table, "schema", "") or ""),
                    "table": str(getattr(table, "name", "") or ""),
                    "synonyms": list(getattr(table, "synonyms", []) or []),
                    "dimensions": [],
                    "measures": [],
                }
                for dimension in table.dimensions or []:
                    table_desc["dimensions"].append(
                        {"name": dimension.name, "synonyms": list(dimension.synonyms or [])}
                    )
                    dimensions.append({"name": dimension.name, "synonyms": list(dimension.synonyms or [])})
                for measure in table.measures or []:
                    table_desc["measures"].append(
                        {"name": measure.name, "synonyms": list(measure.synonyms or [])}
                    )
                    measures.append({"name": measure.name, "synonyms": list(measure.synonyms or [])})
                tables.append(table_desc)

            for metric_name, metric in (getattr(semantic_model, "metrics", {}) or {}).items():
                metric_desc = {"name": str(metric_name), "synonyms": []}
                if hasattr(metric, "synonyms"):
                    metric_desc["synonyms"] = list(getattr(metric, "synonyms", []) or [])
                metrics.append(metric_desc)

        return {
            "id": str(idx),
            "priority": getattr(tool, "priority", 0),
            "name": str(model_name),
            "description": str(description),
            "tags": tags,
            "keywords": keywords,
            "tables": tables,
            "metrics": metrics,
            "dimensions": dimensions,
            "measures": measures,
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
            for table_key, table in getattr(model, "tables", {}).items():
                keywords.add(str(table_key).lower())
                if getattr(table, "schema", None):
                    _consume_values([table.schema])
                if getattr(table, "name", None):
                    _consume_values([table.name])
                _consume_values(table.synonyms or [])

                for dimension in table.dimensions or []:
                    keywords.add(str(dimension.name).lower())
                    _consume_values(dimension.synonyms or [])

                for measure in table.measures or []:
                    keywords.add(str(measure.name).lower())
                    _consume_values(measure.synonyms or [])

            for metric_name, metric in (getattr(model, "metrics", {}) or {}).items():
                keywords.add(str(metric_name).lower())
                if hasattr(metric, "synonyms"):
                    _consume_values(getattr(metric, "synonyms", []) or [])

            for rel in getattr(model, "relationships", []) or []:
                _consume_values([rel.name, rel.from_, rel.to])

        _collect_from_model(semantic_model)

        return keywords


__all__ = ["SemanticToolSelector", "ToolSelectionError"]
