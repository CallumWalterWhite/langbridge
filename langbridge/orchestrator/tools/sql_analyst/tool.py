"""
High-level SQL analyst tool that generates canonical SQL, transpiles it to a target dialect,
and executes the statement through the configured database connector.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import sqlglot

from .interfaces import (
    AnalystQueryRequest,
    AnalystQueryResponse,
    DatabaseConnector,
    LLMClient,
    QueryResult,
    SemanticModel,
)

SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class ToolTelemetry:
    """Capture SQL artefacts for logging/diagnostics."""

    canonical_sql: str
    transpiled_sql: str


class SqlAnalystTool:
    """
    Generate SQL using an LLM with semantic guidance, transpile it to the target dialect,
    and execute through the provided connector.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        semantic_model: SemanticModel,
        connector: DatabaseConnector,
        dialect: str,
        logger: Optional[logging.Logger] = None,
        llm_temperature: float = 0.0,
        priority: int = 0,
    ) -> None:
        self.llm = llm
        self.semantic_model = semantic_model
        self.connector = connector
        self.dialect = dialect
        self.logger = logger or logging.getLogger(__name__)
        self.llm_temperature = llm_temperature
        self.priority = priority
        self._model_summary = self._render_semantic_model()

    @property
    def name(self) -> str:
        return self.semantic_model.name

    def run(self, query_request: AnalystQueryRequest) -> AnalystQueryResponse:
        """
        Synchronous wrapper around the async execution path.
        """

        try:
            return asyncio.run(self.arun(query_request))
        except RuntimeError as exc:  # pragma: no cover - triggered only inside existing event loop
            if "asyncio.run() cannot be called from a running event loop" in str(exc):
                raise RuntimeError(
                    "SqlAnalystTool.run cannot be invoked inside an active event loop. "
                    "Use `await tool.arun(...)` instead."
                ) from exc
            raise

    async def arun(self, query_request: AnalystQueryRequest) -> AnalystQueryResponse:
        """
        Execute the full NL -> SQL -> execution pipeline asynchronously.
        """

        start_ts = time.perf_counter()

        try:
            canonical_sql = self._generate_canonical_sql(query_request)
        except Exception as exc:  # pragma: no cover - defensive: LLM failure surfaces clean error
            self.logger.exception("LLM failed to generate SQL for model %s", self.name)
            return AnalystQueryResponse(
                sql_canonical="",
                sql_executable="",
                dialect=self.dialect,
                model_name=self.name,
                error=f"SQL generation failed: {exc}",
            )

        canonical_sql = canonical_sql.strip()
        canonical_sql = self._extract_sql(canonical_sql)
        sql_validation_error: Optional[str] = None
        try:
            sqlglot.parse_one(canonical_sql, read="postgres")
        except sqlglot.ParseError as exc:
            sql_validation_error = f"Canonical SQL failed to parse: {exc}"

        if sql_validation_error:
            elapsed = int((time.perf_counter() - start_ts) * 1000)
            return AnalystQueryResponse(
                sql_canonical=canonical_sql,
                sql_executable="",
                dialect=self.dialect,
                model_name=self.name,
                error=sql_validation_error,
                execution_time_ms=elapsed,
            )

        try:
            self.logger.debug(
                f"Transpiling {canonical_sql} - postgres -> {self.dialect}"
            )
            transpiled_sql = sqlglot.transpile(
                canonical_sql,
                read="postgres",
                write=self.dialect,
            )[0]
            self.logger.debug("Successful Transpile %s", transpiled_sql)
        except Exception as exc:  # pragma: no cover - sqlglot error path
            elapsed = int((time.perf_counter() - start_ts) * 1000)
            self.logger.exception("Transpile failed for model %s", exc)
            return AnalystQueryResponse(
                sql_canonical=canonical_sql,
                sql_executable="",
                dialect=self.dialect,
                model_name=self.name,
                error=f"Transpile failed: {exc}",
                execution_time_ms=elapsed,
            )

        telemetry = ToolTelemetry(
            canonical_sql=canonical_sql,
            transpiled_sql=transpiled_sql,
        )
        self._log_sql(telemetry)

        result_payload: QueryResult | None = None
        execution_error: Optional[str] = None
        try:
            connector_result = await self.connector.execute(
                transpiled_sql,
                max_rows=query_request.limit,
            )
            result_payload = QueryResult.from_connector(connector_result)
        except Exception as exc:  # pragma: no cover - depends on connector implementation
            self.logger.exception("Execution failed for model %s", self.name)
            execution_error = f"Execution failed: {exc}"

        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)

        return AnalystQueryResponse(
            sql_canonical=canonical_sql,
            sql_executable=transpiled_sql,
            dialect=self.dialect,
            model_name=self.name,
            result=result_payload,
            error=execution_error,
            execution_time_ms=elapsed_ms,
        )

    def _build_prompt(self, request: AnalystQueryRequest) -> str:
        filters_text = ""
        if request.filters:
            filters_kv = ", ".join(f"{key} = {value!r}" for key, value in request.filters.items())
            filters_text = f"Filters to apply: {filters_kv}\n"

        limit_hint = ""
        if request.limit:
            limit_hint = f"Prefer applying LIMIT {request.limit} if appropriate.\n"

        return (
            "You are an expert analytics engineer generating SQL.\n"
            f"{self._model_summary}\n"
            "Rules:\n"
            "- Return a single SELECT statement.\n"
            "- The SQL must target PostgreSQL dialect.\n"
            "- Do not include comments, explanations, or additional text.\n"
            "- Use only entities, joins, metrics, and dimensions defined above.\n"
            """
            - Fully qualify columns as table.column. No SELECT *.
            - Use only relationships defined in the model; INNER JOIN by default.
            - Expand metrics using their expression verbatim.
            - Apply table filters when the request mentions their name or synonyms.
            - Group only by non-aggregated selected dimensions.
            - Prefer a single query; CTEs allowed: base_fact -> joined -> final.
            - Do NOT invent columns/joins. If something is missing, omit it safely.
            - Use ANSI-friendly constructs (CAST, COALESCE, CASE, DATE_PART, standard aggregates) that transpile cleanly.
            - Avoid Postgres-only syntax such as :: type casts, EXTRACT(... FROM ...), DATE_TRUNC, ILIKE, array operators, or JSON-specific features.
            - For date extracts, use strftime function instead.
            """
            f"{limit_hint}"
            f"{filters_text}"
            f"Question: {request.question}\n"
            "Return SQL in PostgreSQL dialect only. No comments or explanation."
        )

    def _generate_canonical_sql(self, request: AnalystQueryRequest) -> str:
        prompt = self._build_prompt(request)
        self.logger.debug("Invoking LLM for model %s", self.name)
        return self.llm.complete(prompt, temperature=self.llm_temperature)

    @staticmethod
    def _extract_sql(raw: str) -> str:
        match = SQL_FENCE_RE.search(raw)
        if match:
            return match.group(1).strip()
        return raw.strip()

    def _render_semantic_model(self) -> str:
        parts: list[str] = [f"Semantic model: {self.semantic_model.name}"]
        if self.semantic_model.description:
            parts.append(f"Description: {self.semantic_model.description}")

        if self.semantic_model.entities:
            parts.append("Entities:")
            for entity_name, entity in self.semantic_model.entities.items():
                parts.append(f"  - {entity_name}")
                table_ref = entity.get("table") or entity.get("name")
                if table_ref:
                    parts.append(f"      table: {table_ref}")
                if "grain" in entity:
                    parts.append(f"      grain: {entity['grain']}")
                columns = entity.get("columns") or entity.get("fields")
                if columns:
                    parts.append("      columns:")
                    for column_name, column_meta in columns.items():
                        if isinstance(column_meta, dict):
                            dtype = column_meta.get("type") or column_meta.get("dtype") or ""
                            role = column_meta.get("role")
                            descriptor = f"{column_name} ({dtype})" if dtype else column_name
                            if role:
                                descriptor += f" [{role}]"
                        else:
                            descriptor = str(column_meta)
                        parts.append(f"        * {descriptor}")

        if self.semantic_model.joins:
            parts.append("Joins:")
            for join in self.semantic_model.joins:
                lhs = join.get("left") or join.get("from")
                rhs = join.get("right") or join.get("to")
                condition = join.get("on") or join.get("condition")
                join_type = join.get("type", "inner")
                parts.append(f"  - {join_type} join {lhs} -> {rhs} on {condition}")

        if self.semantic_model.metrics:
            parts.append("Metrics:")
            for metric_name, metric in self.semantic_model.metrics.items():
                expression = metric.get("expression") or metric.get("sql")
                aggregation = metric.get("aggregation") or metric.get("agg")
                bits = [metric_name]
                if aggregation:
                    bits.append(f"aggregation={aggregation}")
                if expression:
                    bits.append(f"expression={expression}")
                parts.append(f"  - {' | '.join(bits)}")

        if self.semantic_model.dimensions:
            parts.append("Dimensions:")
            for dimension_name, dimension in self.semantic_model.dimensions.items():
                dtype = dimension.get("type")
                desc = f"{dimension_name} ({dtype})" if dtype else dimension_name
                parts.append(f"  - {desc}")

        if self.semantic_model.tags:
            parts.append(f"Tags: {', '.join(self.semantic_model.tags)}")

        return "\n".join(parts)

    def _log_sql(self, telemetry: ToolTelemetry) -> None:
        self.logger.debug("Canonical SQL [%s]: %s", self.name, telemetry.canonical_sql)
        self.logger.debug("Transpiled SQL [%s -> %s]: %s", self.name, self.dialect, telemetry.transpiled_sql)


__all__ = ["SqlAnalystTool"]
