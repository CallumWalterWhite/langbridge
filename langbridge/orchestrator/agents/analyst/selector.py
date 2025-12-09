"""
Semantic-aware selection strategy for SQL analyst tools.
"""


import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from ...tools.sql_analyst.interfaces import AnalystQueryRequest
from ...tools.sql_analyst.tool import SqlAnalystTool

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
    Score tools against a natural language query using semantic model metadata.
    """

    def __init__(self, tools: Sequence[SqlAnalystTool]) -> None:
        if not tools:
            raise ValueError("SemanticToolSelector requires at least one SqlAnalystTool instance.")
        self._tools = list(tools)
        self._keywords = {
            tool: self._extract_keywords(tool.semantic_model)
            for tool in self._tools
        }

    def select(self, request: AnalystQueryRequest) -> SqlAnalystTool:
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
                    priority=tool.priority,
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

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token.lower() for token in TOKEN_RE.findall(text)}

    @staticmethod
    def _score(tokens: set[str], keywords: set[str]) -> float:
        if not keywords:
            return 0.0
        matches = tokens.intersection(keywords)
        return float(len(matches)) / float(len(keywords))

    @staticmethod
    def _extract_keywords(semantic_model) -> set[str]:
        keywords: set[str] = set()
        keywords.add(semantic_model.name.lower())
        for tag in getattr(semantic_model, "tags", []) or []:
            keywords.add(str(tag).lower())

        def _consume_values(values: Iterable[str]) -> None:
            for value in values:
                if not value:
                    continue
                keywords.add(str(value).lower())

        entities = getattr(semantic_model, "entities", {}) or {}
        for entity_name, entity in entities.items():
            keywords.add(str(entity_name).lower())
            if isinstance(entity, dict):
                _consume_values(entity.get("aliases", []) or [])
                _consume_values(entity.get("synonyms", []) or [])
                for column_name, column_meta in (entity.get("columns") or {}).items():
                    keywords.add(str(column_name).lower())
                    if isinstance(column_meta, dict):
                        _consume_values(column_meta.get("synonyms", []) or [])

        for metrics in (getattr(semantic_model, "metrics", {}) or {}).items():
            metric_name, metric = metrics
            keywords.add(str(metric_name).lower())
            if isinstance(metric, dict):
                _consume_values(metric.get("synonyms", []) or [])

        for dimensions in (getattr(semantic_model, "dimensions", {}) or {}).items():
            dimension_name, dimension = dimensions
            keywords.add(str(dimension_name).lower())
            if isinstance(dimension, dict):
                _consume_values(dimension.get("synonyms", []) or [])

        return keywords


__all__ = ["SemanticToolSelector", "ToolSelectionError"]

