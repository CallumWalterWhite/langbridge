"""
Analyst agent that orchestrates NL->SQL generation using semantic models.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from connectors.connector import QueryResult, SqlConnector
from connectors.registry import ConnectorInstanceRegistry
from db.connector import Connector
from semantic.model import SemanticModel

from ..tools.sql_analyst.resolver import ResolvedModel, build_resolved_model
from .sql_tool import SqlAnalystTool, SqlGuidance

TOKEN_REGEX = re.compile(r"\b\w+\b")


@dataclass
class AnalystAgentConfig:
    """
    Configuration for AnalystAgent runtime constraints.
    """

    max_rows: int = 5000
    timeout_s: int = 30
    allow_tables: Optional[List[str]] = None
    deny_tables: Optional[List[str]] = None
    goal: Optional[str] = None
    extra_instructions: Optional[str] = None


@dataclass
class AnalystAgentResultPayload:
    summary: str
    sql: str
    data: Dict[str, Any]
    diagnostics: Dict[str, Any]


class AnalystAgent:
    """
    Agent responsible for selecting semantic models and executing analytical SQL.
    """

    def __init__(
        self,
        *,
        registry: ConnectorInstanceRegistry,
        llm: Optional[BaseChatModel],
        summarizer: Optional[BaseChatModel] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.registry = registry
        self.llm = llm
        self.summarizer = summarizer
        self.logger = logger or logging.getLogger(__name__)
        self._tool_cache: Dict[str, SqlAnalystTool] = {}
        self._connector_cache: Dict[str, SqlConnector] = {}
        self._resolved_model_cache: Dict[str, ResolvedModel] = {}
        self._summary_chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an analytics expert. Summarise SQL results for business stakeholders.",
                    ),
                    ("human", "Question: {question}\nSQL: {sql}\nPreview: {preview}"),
                ]
            )
            | summarizer
            | StrOutputParser()
            if summarizer
            else None
        )

    # ------------------------------------------------------------------ #
    # Semantic model selection helpers
    # ------------------------------------------------------------------ #

    def _model_cache_key(self, model: SemanticModel) -> str:
        candidate_attrs = ("id", "name", "identifier")
        for attr in candidate_attrs:
            value = getattr(model, attr, None)
            if value:
                return str(value)
        if model.connector:
            return f"{model.connector}:{hash(model.model_dump_json())}"
        return f"model:{hash(model.model_dump_json())}"

    def _resolve_model(self, model: SemanticModel) -> ResolvedModel:
        cache_key = self._model_cache_key(model)
        if cache_key not in self._resolved_model_cache:
            self._resolved_model_cache[cache_key] = build_resolved_model(model)
        return self._resolved_model_cache[cache_key]

    def _tokenize(self, text: str) -> set[str]:
        words = set(TOKEN_REGEX.findall(text))
        additional: set[str] = set()
        for word in words:
            if "_" in word:
                additional.update(part for part in word.split("_") if part)
        words.update(additional)
        return words

    def _token_matches(self, token: str, query_words: set[str], query_lower: str) -> bool:
        candidate = token.lower().strip()
        if not candidate:
            return False
        if " " in candidate:
            return candidate in query_lower
        if candidate in query_words:
            return True
        if "_" in candidate:
            parts = [part for part in candidate.split("_") if part]
            return any(part in query_words for part in parts)
        return False

    def _format_match(self, label: str, value: Any) -> str:
        if isinstance(value, tuple):
            value_text = ".".join(part for part in value if part)
        else:
            value_text = str(value)
        return f"{label}:{value_text}"

    def _score_model(
        self,
        query: str,
        model: SemanticModel,
        resolved: ResolvedModel,
    ) -> Tuple[float, List[str]]:
        query_lower = query.lower()
        query_words = self._tokenize(query_lower)
        matches: set[str] = set()
        score = 0.0

        def consume(mapping: Dict[str, Any], weight: float, label: str) -> None:
            nonlocal score
            for token, value in mapping.items():
                if self._token_matches(token, query_words, query_lower):
                    score += weight
                    matches.add(self._format_match(label, value))

        consume(resolved.metric_by_token, 3.0, "metric")
        consume(resolved.column_by_token, 2.0, "column")
        consume(resolved.table_by_token, 1.0, "table")
        consume(resolved.filter_by_token, 1.5, "filter")

        descriptor_candidates = [model.description, model.connector]
        for descriptor in descriptor_candidates:
            if descriptor and self._token_matches(descriptor, query_words, query_lower):
                score += 0.5
                matches.add(self._format_match("descriptor", descriptor))

        return score, sorted(matches)

    def _describe_model(self, model: SemanticModel) -> str:
        name_like_attrs = ("name", "title", "identifier")
        for attr in name_like_attrs:
            value = getattr(model, attr, None)
            if value:
                descriptor = str(value)
                break
        else:
            descriptor = model.description or ""

        if not descriptor:
            tables = list(model.tables.keys())
            descriptor = tables[0] if tables else "semantic_model"

        if model.connector:
            return f"{descriptor} [{model.connector}]"
        return descriptor

    def _select_semantic_model(
        self,
        query: str,
        models: Sequence[SemanticModel],
    ) -> Tuple[SemanticModel, List[Dict[str, Any]]]:
        if not models:
            raise RuntimeError("No semantic models available for AnalystAgent.")

        candidates: List[Dict[str, Any]] = []
        for model in models:
            resolved = self._resolve_model(model)
            score, matches = self._score_model(query, model, resolved)
            candidates.append(
                {
                    "model": model,
                    "score": score,
                    "matches": matches,
                }
            )

        candidates.sort(key=lambda entry: entry["score"], reverse=True)
        ranking: List[Dict[str, Any]] = []
        for idx, entry in enumerate(candidates):
            ranking.append(
                {
                    "model": self._describe_model(entry["model"]),
                    "score": entry["score"],
                    "matches": entry["matches"][:5],
                    "selected": idx == 0,
                }
            )

        return candidates[0]["model"], ranking

    # ------------------------------------------------------------------ #
    # Connector/tool helpers
    # ------------------------------------------------------------------ #

    def _get_connector_for_model(self, model: SemanticModel) -> SqlConnector:
        if not model.connector:
            raise RuntimeError("Semantic model is missing a connector reference.")

        if model.connector in self._connector_cache:
            return self._connector_cache[model.connector]

        try:
            connector = self.registry.get(model.connector)
        except KeyError as exc:
            raise RuntimeError(
                f"Connector '{model.connector}' not found in registry for selected semantic model."
            ) from exc

        self._connector_cache[model.connector] = connector
        return connector

    def _get_tool(self, model: SemanticModel, connector: SqlConnector) -> SqlAnalystTool:
        cache_key = self._model_cache_key(model)
        if cache_key in self._tool_cache:
            return self._tool_cache[cache_key]
        tool = SqlAnalystTool(connector=connector, semantic_model=model, llm=self.llm, logger=self.logger)
        self._tool_cache[cache_key] = tool
        return tool

    async def _generate_summary(
        self,
        question: str,
        sql: str,
        result: QueryResult,
    ) -> str:
        if not self._summary_chain:
            return f"Retrieved {result.rowcount} rows across {len(result.columns)} columns."
        preview_rows = result.rows[: min(len(result.rows), 5)]
        preview = {"columns": result.columns, "rows": preview_rows}
        return await self._summary_chain.ainvoke(
            {"question": question, "sql": sql, "preview": preview}
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def run(
        self,
        *,
        query: str,
        available_semantic_models: Optional[Sequence[SemanticModel]] = None,
        available_connectors: Optional[Sequence[Connector]] = None,  # noqa: ARG003 - reserved for future use
        config: Optional[AnalystAgentConfig] = None,
        params: Optional[Dict[str, Any]] = None,
        is_sql: bool = False,
    ) -> AnalystAgentResultPayload:
        """
        Execute the full NL -> SQL -> execution pipeline.
        """

        del available_connectors  # Explicitly unused until we materialise DB connectors via the registry.

        models = list(available_semantic_models or [])
        config = config or AnalystAgentConfig()

        selected_model, ranking = self._select_semantic_model(query, models)
        connector = self._get_connector_for_model(selected_model)
        tool = self._get_tool(selected_model, connector)

        guidance = SqlGuidance(
            goal=config.goal or query,
            allow_tables=config.allow_tables,
            deny_tables=config.deny_tables,
            extra_instructions=config.extra_instructions,
            dialect=tool.connector.DIALECT,
            max_rows=config.max_rows,
        )

        if not is_sql:
            if self.llm is None:
                raise RuntimeError("No LLM configured to translate natural language queries.")
            sql = (await tool.build_sql_from_nl(query, guidance)).strip()
        else:
            sql = query.strip()

        tool.validate_sql(sql, guidance)

        start = time.perf_counter()
        result = await tool.run_sql(sql, params=params, guidance=guidance)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        summary = await self._generate_summary(query, sql, result)

        selection_diag = ranking[: min(len(ranking), 3)]

        payload = AnalystAgentResultPayload(
            summary=summary.strip(),
            sql=sql,
            data=result.json_safe(),
            diagnostics={
                "elapsed_ms": elapsed_ms,
                "rowcount": result.rowcount,
                "dialect": tool.connector.dialect,
                "semantic_model": {
                    "name": self._describe_model(selected_model),
                    "connector": selected_model.connector,
                    "tables": list(selected_model.tables.keys()),
                },
                "model_candidates": selection_diag,
            },
        )
        return payload


__all__ = ["AnalystAgent", "AnalystAgentConfig", "AnalystAgentResultPayload"]
