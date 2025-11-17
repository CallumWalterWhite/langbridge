"""
High-level SQL analyst tool that generates canonical SQL, transpiles it to a target dialect,
and executes the statement through the configured database connector.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import sqlglot

from .interfaces import (
    AnalystQueryRequest,
    AnalystQueryResponse,
    DatabaseConnector,
    LLMClient,
    QueryResult,
    SemanticModel,
)
from utils.embedding_provider import EmbeddingProvider

SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class ToolTelemetry:
    """Capture SQL artefacts for logging/diagnostics."""

    canonical_sql: str
    transpiled_sql: str


@dataclass(slots=True)
class VectorizedValue:
    value: str
    embedding: List[float]


@dataclass(slots=True)
class VectorizedColumn:
    entity: str
    column: str
    values: List[VectorizedValue]


@dataclass(slots=True)
class VectorMatch:
    entity: str
    column: str
    value: str
    similarity: float
    source_text: str


VECTOR_SIMILARITY_THRESHOLD = 0.83


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
        embedder: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.llm = llm
        self.semantic_model = semantic_model
        self.connector = connector
        self.dialect = dialect
        self.logger = logger or logging.getLogger(__name__)
        self.llm_temperature = llm_temperature
        self.priority = priority
        self._model_summary = self._render_semantic_model()
        self.embedder = embedder
        self._vector_columns = self._extract_vector_columns()

    @property
    def name(self) -> str:
        return self.semantic_model.name

    def _extract_vector_columns(self) -> List[VectorizedColumn]:
        catalog: List[VectorizedColumn] = []
        entities = self.semantic_model.entities or {}
        for entity_name, entity_meta in entities.items():
            if not isinstance(entity_meta, dict):
                continue
            columns = entity_meta.get("columns") or {}
            for column_name, column_meta in columns.items():
                if not isinstance(column_meta, dict):
                    continue
                if not column_meta.get("vectorized"):
                    continue
                index_meta = column_meta.get("vector_index") or {}
                values_meta = index_meta.get("values") or []
                vector_values: List[VectorizedValue] = []
                for entry in values_meta:
                    value = str((entry or {}).get("value", "")).strip()
                    embedding = (entry or {}).get("embedding")
                    if not value or not isinstance(embedding, list):
                        continue
                    try:
                        vector = [float(component) for component in embedding]
                    except (TypeError, ValueError):
                        continue
                    vector_values.append(VectorizedValue(value=value, embedding=vector))
                if vector_values:
                    catalog.append(
                        VectorizedColumn(
                            entity=entity_name,
                            column=column_name,
                            values=vector_values,
                        )
                    )
        return catalog

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
        active_request = query_request

        if self.embedder and self._vector_columns:
            try:
                active_request = await self._maybe_augment_request_with_vectors(query_request)
            except Exception as exc:  # pragma: no cover - defensive guard
                self.logger.warning("Vector search failed; continuing without augmentation: %s", exc)
                active_request = query_request

        try:
            canonical_sql = self._generate_canonical_sql(active_request)
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
                max_rows=active_request.limit,
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

    async def _maybe_augment_request_with_vectors(self, request: AnalystQueryRequest) -> AnalystQueryRequest:
        if not self.embedder or not self._vector_columns:
            return request
        matches = await self._resolve_vector_matches(request.question)
        if not matches:
            return request

        augmented_question = self._augment_question_with_matches(request.question, matches)
        filters: Dict[str, Any] = dict(request.filters or {})
        for match in matches:
            key = f"{match.entity}.{match.column}"
            filters[key] = match.value

        return request.model_copy(
            update={
                "question": augmented_question,
                "filters": filters or request.filters,
            }
        )

    async def _resolve_vector_matches(self, question: str) -> List[VectorMatch]:
        phrases = self._extract_candidate_phrases(question)
        if not phrases or not self.embedder:
            return []

        embeddings = await self.embedder.embed(phrases)
        if not embeddings:
            return []

        phrase_vectors = list(zip(phrases, embeddings))
        matches: List[VectorMatch] = []
        for column in self._vector_columns:
            best_match: Optional[VectorMatch] = None
            for phrase, vector in phrase_vectors:
                for candidate in column.values:
                    similarity = _cosine_similarity(vector, candidate.embedding)
                    if similarity is None:
                        continue
                    if not best_match or similarity > best_match.similarity:
                        best_match = VectorMatch(
                            entity=column.entity,
                            column=column.column,
                            value=candidate.value,
                            similarity=similarity,
                            source_text=phrase,
                        )
            if best_match and best_match.similarity >= VECTOR_SIMILARITY_THRESHOLD:
                matches.append(best_match)
        return sorted(matches, key=lambda match: match.similarity, reverse=True)[:3]

    def _extract_candidate_phrases(self, question: str) -> List[str]:
        base = question.strip()
        candidates: List[str] = []
        seen: set[str] = set()

        def _add(text: str) -> None:
            cleaned = text.strip()
            if not cleaned:
                return
            lowered = cleaned.lower()
            if lowered in seen:
                return
            seen.add(lowered)
            candidates.append(cleaned)

        if base:
            _add(base)

        for quoted in re.findall(r'"([^"]+)"', question):
            _add(quoted)
        for quoted in re.findall(r"'([^']+)'", question):
            _add(quoted)
        for keyword_match in re.findall(
            r"\b(?:in|at|for|from|by|with)\s+([A-Za-z0-9][^,.;:]+)",
            question,
            flags=re.IGNORECASE,
        ):
            cleaned = re.split(r"[.,;:]", keyword_match, 1)[0]
            _add(cleaned)
        for capitalized in re.findall(r"\b([A-Z][\w-]*(?:\s+[A-Z][\w-]*)+)\b", question):
            _add(capitalized)

        return candidates[:8]

    @staticmethod
    def _augment_question_with_matches(question: str, matches: List[VectorMatch]) -> str:
        hints = "\n".join(
            f"- Use {match.entity}.{match.column} = '{match.value}' "
            f"(matched phrase '{match.source_text}', similarity {match.similarity:.2f})"
            for match in matches
        )
        prefix = question.strip() or question
        if not hints:
            return prefix
        return (
            f"{prefix}\n\nResolved entities from semantic vector search:\n"
            f"{hints}\nApply these as explicit filters in the SQL."
        )

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


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> Optional[float]:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return None
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for component_a, component_b in zip(vec_a, vec_b):
        dot += component_a * component_b
        norm_a += component_a * component_a
        norm_b += component_b * component_b
    if norm_a == 0 or norm_b == 0:
        return None
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
