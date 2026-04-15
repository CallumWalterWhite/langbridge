"""
Federated analytical tool for dataset-backed and semantic-model-backed SQL generation.
"""
import asyncio
import inspect
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import sqlglot
from sqlglot import exp

from langbridge.orchestrator.definitions import AnalystQueryScopePolicy
from langbridge.runtime.services.semantic_vector_search_service import (
    SemanticVectorSearchService,
)
from langbridge.orchestrator.llm.provider import LLMProvider
from langbridge.runtime.embeddings import EmbeddingProvider
from langbridge.runtime.events import (
    AgentEventVisibility,
    AgentEventEmitter,
)
from langbridge.runtime.models import SqlQueryScope
from .prompts import (
    SQL_ORCHESTRATION_INSTRUCTION,
    SEMANTIC_SQL_ORCHESTRATION_INSTRUCTION,
    DATASET_SQL_ORCHESTRATION_INSTRUCTION,
)
from .renderer import render_analysis_context
from .interfaces import (
    AnalyticalContext,
    AnalyticalQueryExecutionFailure,
    AnalyticalQueryExecutionResult,
    AnalyticalQueryExecutor,
    AnalyticalField,
    AnalyticalMetric,
    AnalystExecutionOutcome,
    AnalystOutcomeStage,
    AnalystOutcomeStatus,
    AnalystQueryRequest,
    AnalystQueryResponse,
    QueryResult,
    SemanticModel,
    SemanticModelLike,
)

SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
VECTOR_SIMILARITY_THRESHOLD = 0.83
VECTOR_SEARCH_TOP_K = 3
MAX_VECTOR_MATCHES = 10
MAX_CANDIDATE_PHRASES = 8
RETRY_BACKOFF_SECONDS = 1
TEMPORAL_TYPE_NAMES = {"date", "datetime", "time", "timestamp", "timestamptz"}


@dataclass(slots=True)
class ToolTelemetry:
    canonical_sql: str
    executable_sql: str


@dataclass(slots=True)
class VectorMatch:
    entity: str
    column: str
    value: str
    similarity: float
    source_text: str


class SqlAnalystTool:
    """
    Generate federated SQL for an analytical asset and execute it through the
    dataset federation layer.
    """

    def __init__(
        self,
        *,
        llm: LLMProvider,
        context: AnalyticalContext,
        query_executor: AnalyticalQueryExecutor,
        semantic_model: SemanticModelLike | None = None,
        binding_name: str | None = None,
        binding_description: str | None = None,
        query_scope_policy: AnalystQueryScopePolicy = AnalystQueryScopePolicy.semantic_preferred,
        logger: logging.Logger | None = None,
        llm_temperature: float = 0.0,
        priority: int = 0,
        embedder: Optional[EmbeddingProvider] = None,
        event_emitter: Optional[AgentEventEmitter] = None,
        semantic_vector_search_service: SemanticVectorSearchService | None = None,
        semantic_vector_search_workspace_id: uuid.UUID | None = None,
        semantic_vector_search_model_id: uuid.UUID | None = None,
    ) -> None:
        self.llm = llm
        self.context = context
        self.semantic_model = semantic_model
        self._query_executor = query_executor
        self.binding_name = str(binding_name or context.asset_name or "analytical_binding").strip() or "analytical_binding"
        self.binding_description = str(binding_description or "").strip() or None
        self.query_scope_policy = query_scope_policy
        self.dialect = str(context.dialect or "postgres").strip().lower() or "postgres"
        self.logger = logger or logging.getLogger(__name__)
        self.llm_temperature = llm_temperature
        self.priority = priority
        self.embedder = embedder
        self._event_emitter = event_emitter
        self._semantic_vector_search_service = semantic_vector_search_service
        self._semantic_vector_search_workspace_id = semantic_vector_search_workspace_id
        self._semantic_vector_search_model_id = semantic_vector_search_model_id

    @property
    def name(self) -> str:
        return self.context.asset_name or "analytical_asset"

    @property
    def asset_type(self) -> str:
        return self.context.asset_type

    @property
    def query_scope(self) -> SqlQueryScope:
        return self.context.query_scope

    def describe_for_selection(self, *, tool_id: str) -> dict[str, Any]:
        return {
            "id": tool_id,
            "binding_name": self.binding_name,
            "binding_description": self.binding_description,
            "query_scope_policy": self.query_scope_policy.value,
            "query_scope": self.query_scope.value,
            "priority": self.priority,
            "asset_type": self.context.asset_type,
            "asset_name": self.context.asset_name,
            "description": self.context.description,
            "tags": list(self.context.tags or []),
            "execution_mode": self.context.execution_mode,
            "datasets": [
                {
                    "dataset_id": dataset.dataset_id,
                    "dataset_name": dataset.dataset_name,
                    "sql_alias": dataset.sql_alias,
                    "source_kind": dataset.source_kind,
                    "storage_kind": dataset.storage_kind,
                    "columns": [column.name for column in dataset.columns],
                }
                for dataset in self.context.datasets
            ],
            "tables": list(self.context.tables or []),
            "dimensions": [field.model_dump(mode="json") for field in self.context.dimensions],
            "measures": [field.model_dump(mode="json") for field in self.context.measures],
            "metrics": [metric.model_dump(mode="json") for metric in self.context.metrics],
            "relationships": list(self.context.relationships or []),
            "keywords": sorted(self.selection_keywords()),
        }

    def selection_keywords(self) -> set[str]:
        keywords: set[str] = set()

        def _consume(value: str | None) -> None:
            if value is None:
                return
            normalized = str(value).strip().lower()
            if normalized:
                keywords.add(normalized)

        def _consume_field(field: AnalyticalField) -> None:
            _consume(field.name)
            for synonym in field.synonyms or []:
                _consume(synonym)

        def _consume_metric(metric: AnalyticalMetric) -> None:
            _consume(metric.name)
            _consume(metric.description)

        _consume(self.context.asset_name)
        _consume(self.context.description)
        for tag in self.context.tags or []:
            _consume(tag)
        for dataset in self.context.datasets:
            _consume(dataset.dataset_name)
            _consume(dataset.sql_alias)
            _consume(dataset.description)
            _consume(dataset.source_kind)
            _consume(dataset.storage_kind)
            for column in dataset.columns:
                _consume(column.name)
                _consume(column.description)
                _consume(column.data_type)
        for table in self.context.tables or []:
            _consume(table)
        for relationship in self.context.relationships or []:
            _consume(relationship)
        for field in self.context.dimensions:
            _consume_field(field)
        for field in self.context.measures:
            _consume_field(field)
        for metric in self.context.metrics:
            _consume_metric(metric)
        return keywords

    def run(self, query_request: AnalystQueryRequest) -> AnalystQueryResponse:
        try:
            return asyncio.run(self.arun(query_request))
        except RuntimeError as exc:  # pragma: no cover
            if "asyncio.run() cannot be called from a running event loop" in str(exc):
                raise RuntimeError(
                    "SqlAnalystTool.run cannot be invoked inside an active event loop. "
                    "Use `await tool.arun(...)` instead."
                ) from exc
            raise

    async def arun(self, query_request: AnalystQueryRequest) -> AnalystQueryResponse:
        request = query_request.model_copy(deep=True)
        max_retries = max(int(request.error_retries or 0), 0)

        for attempt in range(max_retries + 1):
            response = await self._execute(request)
            outcome = response.outcome
            if (
                outcome is None
                or not outcome.recoverable
                or outcome.status not in {AnalystOutcomeStatus.query_error, AnalystOutcomeStatus.execution_error}
                or attempt >= max_retries
            ):
                return response

            await self._emit_event(
                event_type="AnalyticalToolExecutionError",
                message=outcome.message or response.error or "Analytical execution failed.",
                visibility=AgentEventVisibility.public,
                details=self._event_details(
                    error=outcome.message or response.error,
                    retry_count=attempt,
                    max_retries=max_retries,
                ),
            )
            self.logger.warning(
                "Execution error for asset %s: %s. Retrying (%d/%d)...",
                self.name,
                outcome.message or response.error,
                attempt + 1,
                max_retries,
            )
            if outcome.message:
                request.error_history.append(outcome.message)
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)

        raise RuntimeError(f"Execution failed for asset {self.name} after {max_retries} retries.")

    async def _execute(self, query_request: AnalystQueryRequest) -> AnalystQueryResponse:
        await self._emit_event(
            event_type="AnalyticalToolStarted",
            message="Analyzing the selected analytical asset.",
            visibility=AgentEventVisibility.public,
            details=self._event_details(
                execution_mode=self.context.execution_mode,
                query_scope=self.query_scope.value,
            ),
        )
        start_ts = time.perf_counter()
        active_request = await self._augment_request(query_request)

        try:
            canonical_sql = await self._generate_canonical_sql(active_request)
        except Exception as exc:  # pragma: no cover
            self.logger.exception("LLM failed to generate SQL for asset %s", self.name)
            await self._emit_event(
                event_type="AnalyticalSqlGenerationFailed",
                message="Failed to generate SQL from your request.",
                visibility=AgentEventVisibility.public,
                details=self._event_details(error=str(exc)),
            )
            return self._build_response(
                sql_canonical="",
                sql_executable="",
                outcome=self._build_outcome(
                    status=AnalystOutcomeStatus.query_error,
                    stage=AnalystOutcomeStage.query,
                    message=f"SQL generation failed: {exc}",
                    original_error=str(exc),
                    recoverable=True,
                    terminal=False,
                ),
                elapsed_ms=None,
            )

        canonical_sql = self._prepare_canonical_sql(canonical_sql)
        await self._emit_event(
            event_type="AnalyticalSqlGenerated",
            message="A scoped analytical query was generated.",
            visibility=AgentEventVisibility.internal,
            details=self._event_details(
                sql_canonical=canonical_sql,
                query_scope=self.query_scope.value,
            ),
        )

        await self._emit_event(
            event_type="AnalyticalSqlExecutionStarted",
            message="Running analytical query in the selected scope.",
            visibility=AgentEventVisibility.public,
            details=self._event_details(
                dialect=self.dialect,
                execution_mode=self.context.execution_mode,
                query_scope=self.query_scope.value,
                max_rows=active_request.limit,
            ),
        )

        execution_result: AnalyticalQueryExecutionResult | None = None
        execution_outcome: AnalystExecutionOutcome | None = None
        executable_sql = ""
        try:
            execution_result = await self._query_executor.execute_query(
                query=canonical_sql,
                query_dialect=self.dialect,
                requested_limit=active_request.limit,
            )
            executable_sql = execution_result.executable_query
            self._log_sql(ToolTelemetry(canonical_sql=canonical_sql, executable_sql=executable_sql))
            await self._emit_event(
                event_type="AnalyticalSqlExecutionPrepared",
                message="Prepared analytical statement for execution.",
                visibility=AgentEventVisibility.internal,
                details=self._event_details(
                    dialect=self.dialect,
                    sql_canonical=canonical_sql,
                    sql_executable=executable_sql,
                    query_scope=self.query_scope.value,
                    max_rows=active_request.limit,
                ),
            )
            await self._emit_event(
                event_type="AnalyticalSqlExecutionCompleted",
                message="Analytical query completed.",
                visibility=AgentEventVisibility.public,
                details=self._event_details(
                    row_count=execution_result.result.rowcount,
                    elapsed_ms=execution_result.result.elapsed_ms,
                    query_scope=self.query_scope.value,
                ),
            )
        except AnalyticalQueryExecutionFailure as exc:
            executable_sql = str(exc.metadata.get("executable_query") or "")
            await self._emit_event(
                event_type="AnalyticalSqlExecutionFailed",
                message=f"Analytical query failed. Error: {exc.message}",
                visibility=AgentEventVisibility.public,
                details=self._event_details(
                    error=exc.message,
                    query_scope=self.query_scope.value,
                ),
            )
            execution_outcome = self._build_outcome(
                status=(
                    AnalystOutcomeStatus.query_error
                    if exc.stage == AnalystOutcomeStage.query
                    else AnalystOutcomeStatus.execution_error
                ),
                stage=exc.stage,
                message=exc.message,
                original_error=exc.original_error,
                recoverable=exc.recoverable,
                terminal=False,
                metadata=dict(exc.metadata or {}),
            )
        except Exception as exc:  # pragma: no cover
            self.logger.exception("Analytical execution failed for asset %s", self.name)
            await self._emit_event(
                event_type="AnalyticalSqlExecutionFailed",
                message=f"Analytical query failed. Error: {str(exc)}",
                visibility=AgentEventVisibility.public,
                details=self._event_details(
                    error=str(exc),
                    query_scope=self.query_scope.value,
                ),
            )
            execution_outcome = self._build_outcome(
                status=AnalystOutcomeStatus.execution_error,
                stage=AnalystOutcomeStage.execution,
                message=f"Execution failed: {exc}",
                original_error=str(exc),
                recoverable=False,
                terminal=False,
            )

        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        if execution_outcome is None and execution_result is not None:
            if execution_result.result.rowcount or len(execution_result.result.rows):
                execution_outcome = self._build_outcome(
                    status=AnalystOutcomeStatus.success,
                    stage=AnalystOutcomeStage.result,
                    terminal=True,
                    metadata=dict(execution_result.metadata or {}),
                )
            else:
                execution_outcome = self._build_outcome(
                    status=AnalystOutcomeStatus.empty_result,
                    stage=AnalystOutcomeStage.result,
                    message="No rows matched the query.",
                    recoverable=True,
                    terminal=False,
                    metadata=dict(execution_result.metadata or {}),
                )
        return self._build_response(
            sql_canonical=canonical_sql,
            sql_executable=executable_sql,
            result=execution_result.result if execution_result is not None else None,
            outcome=execution_outcome,
            elapsed_ms=elapsed_ms,
        )

    def _event_details(self, **extra: Any) -> dict[str, Any]:
        details = {
            "binding_name": self.binding_name,
            "asset_name": self.name,
            "asset_type": self.asset_type,
            "query_scope": self.query_scope.value,
        }
        details.update(extra)
        return details

    async def _augment_request(self, request: AnalystQueryRequest) -> AnalystQueryRequest:
        if not self.embedder or self._semantic_vector_search_service is None:
            return request
        try:
            return await self._maybe_augment_request_with_vectors(request)
        except Exception as exc:  # pragma: no cover
            self.logger.warning("Vector search failed; continuing without augmentation: %s", exc)
            return request

    def _prepare_canonical_sql(self, raw_sql: str) -> str:
        canonical_sql = self._extract_sql(raw_sql.strip())
        if self.query_scope == SqlQueryScope.semantic:
            return canonical_sql
        canonical_sql = self._expand_semantic_measure_references(canonical_sql)
        return self._normalize_temporal_predicates(canonical_sql)

    def _build_sql_orchestration_instructions(self) -> str:
        orchestration = getattr(self.semantic_model, "orchestration", None)
        if orchestration is not None:
            return SQL_ORCHESTRATION_INSTRUCTION.format(instruction=orchestration)
        return ""

    def _build_error_hints(self, error_history: list[str]) -> str:
        if not error_history:
            return ""
        hints = "\n".join(f"- {error}" for error in error_history[-3:])
        return f"Previous execution errors:\n{hints}\nUse these hints to avoid repeating the same mistakes.\n"

    async def _generate_canonical_sql(self, request: AnalystQueryRequest) -> str:
        prompt = self._build_prompt(request)
        self.logger.info("Invoking LLM for analytical asset %s", self.name)
        self.logger.debug("Prompt for %s:\n%s", self.name, prompt)
        return await self._complete_prompt(prompt)

    async def _complete_prompt(self, prompt: str) -> str:
        async_completion = getattr(self.llm, "acomplete", None)
        if callable(async_completion):
            result = async_completion(prompt, temperature=self.llm_temperature)
            if inspect.isawaitable(result):
                return await result
            return result

        completion = getattr(self.llm, "complete", None)
        if callable(completion):
            return await asyncio.to_thread(
                completion,
                prompt,
                temperature=self.llm_temperature,
            )

        raise AttributeError("Configured LLM provider does not support complete or acomplete.")

    def _build_response(
        self,
        *,
        sql_canonical: str,
        sql_executable: str,
        result: QueryResult | None = None,
        outcome: AnalystExecutionOutcome | None = None,
        elapsed_ms: int | None = None,
    ) -> AnalystQueryResponse:
        return AnalystQueryResponse(
            analysis_path=self.context.asset_type,
            query_scope=self.query_scope,
            execution_mode=self.context.execution_mode,
            asset_type=self.context.asset_type,
            asset_id=self.context.asset_id,
            asset_name=self.context.asset_name,
            selected_semantic_model_id=(
                self.context.asset_id
                if self.context.asset_type == "semantic_model"
                else None
            ),
            sql_canonical=sql_canonical,
            sql_executable=sql_executable,
            dialect=self.dialect,
            selected_datasets=list(self.context.datasets),
            result=result,
            error=outcome.message if outcome else None,
            execution_time_ms=elapsed_ms,
            outcome=outcome,
        )

    def _build_outcome(
        self,
        *,
        status: AnalystOutcomeStatus,
        stage: AnalystOutcomeStage,
        message: str | None = None,
        original_error: str | None = None,
        recoverable: bool = False,
        terminal: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> AnalystExecutionOutcome:
        return AnalystExecutionOutcome(
            status=status,
            stage=stage,
            message=message,
            original_error=original_error,
            recoverable=recoverable,
            terminal=terminal,
            selected_tool_name=self.name,
            selected_asset_id=self.context.asset_id,
            selected_asset_name=self.context.asset_name,
            selected_asset_type=self.context.asset_type,
            attempted_query_scope=self.query_scope,
            final_query_scope=self.query_scope,
            selected_semantic_model_id=(
                self.context.asset_id
                if self.context.asset_type == "semantic_model"
                else None
            ),
            selected_dataset_ids=[dataset.dataset_id for dataset in self.context.datasets],
            metadata=dict(metadata or {}),
        )

    async def _emit_event(
        self,
        *,
        event_type: str,
        message: str,
        visibility: AgentEventVisibility,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not self._event_emitter:
            return
        try:
            await self._event_emitter.emit(
                event_type=event_type,
                message=message,
                visibility=visibility,
                source=f"tool:analyst:{self.name}",
                details=details,
            )
        except Exception as exc:  # pragma: no cover
            self.logger.warning("Failed to emit analytical tool event %s: %s", event_type, exc)

    def _build_prompt(self, request: AnalystQueryRequest) -> str:
        conversation_text = ""
        if request.conversation_context:
            conversation_text = f"Conversation context:\n{request.conversation_context}\n"

        filters_text = ""
        if request.filters:
            filters_kv = ", ".join(f"{key} = {value!r}" for key, value in request.filters.items())
            filters_text = f"Filters to apply: {filters_kv}\n"

        limit_hint = ""
        if request.limit:
            limit_hint = f"Prefer applying LIMIT {request.limit} if appropriate.\n"

        search_text = ""
        if request.semantic_search_result_prompts:
            search_text = "Search hints:\n" + "\n".join(request.semantic_search_result_prompts) + "\n"

        shared_sections = (
            f"{render_analysis_context(self.context, self.semantic_model)}\n"
            f"{self._build_sql_orchestration_instructions()}"
            f"{self._build_error_hints(request.error_history)}"
            f"{limit_hint}"
            f"{filters_text}"
            f"{conversation_text}"
            f"{search_text}"
            f"Question: {request.question}\n"
        )

        if self.query_scope == SqlQueryScope.semantic:
            relation_name = self._semantic_relation_name()
            return SEMANTIC_SQL_ORCHESTRATION_INSTRUCTION.format(
                shared_sections=shared_sections,
                relation_name=relation_name,
            )

        return DATASET_SQL_ORCHESTRATION_INSTRUCTION.format(shared_sections=shared_sections)

    def _semantic_relation_name(self) -> str:
        relation_name = str(self.context.asset_name or "").strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", relation_name):
            return relation_name
        escaped = relation_name.replace('"', '""')
        return f'"{escaped}"'

    async def _maybe_augment_request_with_vectors(self, request: AnalystQueryRequest) -> AnalystQueryRequest:
        if not self.embedder or self._semantic_vector_search_service is None:
            return request
        if not self._semantic_vector_search_workspace_id or not self._semantic_vector_search_model_id:
            return request
        matches = await self._resolve_vector_matches(request.question)
        if not matches:
            return request

        augmented_question = self._augment_question_with_matches(request.question, matches)
        filters: Dict[str, Any] = dict(request.filters or {})
        prompts = list(request.semantic_search_result_prompts or [])
        for match in matches:
            key = f"{match.entity}.{match.column}"
            filters[key] = match.value
            prompts.append(
                f"{match.entity}.{match.column} ~= '{match.value}' "
                f"(matched '{match.source_text}', similarity {match.similarity:.2f})"
            )

        return request.model_copy(
            update={
                "question": augmented_question,
                "filters": filters or request.filters,
                "semantic_search_result_prompts": prompts or request.semantic_search_result_prompts,
            }
        )

    async def _resolve_vector_matches(self, question: str) -> List[VectorMatch]:
        phrases = self._extract_candidate_phrases(question)
        if (
            not phrases
            or not self.embedder
            or self._semantic_vector_search_service is None
            or not self._semantic_vector_search_workspace_id
            or not self._semantic_vector_search_model_id
        ):
            return []

        raw_hits = await self._semantic_vector_search_service.search(
            workspace_id=self._semantic_vector_search_workspace_id,
            semantic_model_id=self._semantic_vector_search_model_id,
            queries=phrases,
            embedding_provider=self.embedder,
            top_k=VECTOR_SEARCH_TOP_K,
        )
        if not raw_hits:
            return []

        matches = [
            VectorMatch(
                entity=hit.dataset_key,
                column=hit.dimension_name,
                value=hit.matched_value,
                similarity=hit.score,
                source_text=hit.source_text,
            )
            for hit in raw_hits
            if hit.score >= VECTOR_SIMILARITY_THRESHOLD
        ]
        return matches[:MAX_VECTOR_MATCHES]

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
            cleaned = re.split(r"[.,;:?!]", keyword_match, maxsplit=1)[0]
            _add(cleaned)
        for capitalized in re.findall(r"\b([A-Z][\w-]*(?:\s+[A-Z][\w-]*)+)\b", question):
            _add(capitalized)

        return candidates[:MAX_CANDIDATE_PHRASES]

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
            f"{prefix}\n\nResolved entities from vector search:\n"
            f"{hints}\nApply these as explicit filters in the SQL."
        )

    @staticmethod
    def _extract_sql(raw: str) -> str:
        match = SQL_FENCE_RE.search(raw)
        if match:
            return match.group(1).strip()
        return raw.strip()

    def _log_sql(self, telemetry: ToolTelemetry) -> None:
        self.logger.debug("Canonical SQL [%s]: %s", self.name, telemetry.canonical_sql)
        self.logger.debug("Executable SQL [%s -> %s]: %s", self.name, self.dialect, telemetry.executable_sql)

    def _expand_semantic_measure_references(self, sql: str) -> str:
        if self.semantic_model is None:
            return sql

        try:
            expression = sqlglot.parse_one(sql, read="postgres")
        except sqlglot.ParseError:
            return sql

        measure_map = {
            (str(table_key).strip().lower(), str(measure.name).strip().lower()): str(
                measure.expression or measure.name
            ).strip()
            for table_key, table in (getattr(self.semantic_model, "tables", {}) or {}).items()
            for measure in (table.measures or [])
            if str(measure.expression or measure.name).strip()
        }
        if not measure_map:
            return sql

        def _transform(node: exp.Expression) -> exp.Expression:
            if not isinstance(node, exp.Column):
                return node
            table_name = str(node.table or "").strip().lower()
            column_name = str(node.name or "").strip().lower()
            if not table_name or not column_name:
                return node
            expression_sql = measure_map.get((table_name, column_name))
            if not expression_sql or expression_sql.lower() == column_name:
                return node
            replacement = self._build_measure_expression(
                table_name=table_name,
                expression_sql=expression_sql,
            )
            return replacement or node

        return expression.transform(_transform).sql(dialect="postgres")

    def _build_measure_expression(
        self,
        *,
        table_name: str,
        expression_sql: str,
    ) -> exp.Expression | None:
        try:
            expression = sqlglot.parse_one(expression_sql, read="postgres")
        except sqlglot.ParseError:
            return None

        def _qualify(node: exp.Expression) -> exp.Expression:
            if isinstance(node, exp.Column) and not node.table:
                return sqlglot.parse_one(f"{table_name}.{node.name}", read="postgres")
            return node

        return expression.transform(_qualify)

    def _normalize_temporal_predicates(self, sql: str) -> str:
        temporal_columns = self._temporal_columns_by_name()
        if not temporal_columns:
            return sql

        try:
            expression = sqlglot.parse_one(sql, read="postgres")
        except sqlglot.ParseError:
            return sql

        def _transform(node: exp.Expression) -> exp.Expression:
            if not isinstance(node, exp.Column):
                return node
            cast_target = self._cast_target_for_column(node=node, temporal_columns=temporal_columns)
            if cast_target is None:
                return node
            if self._has_explicit_temporal_cast(node):
                return node
            if not self._is_temporal_predicate_context(node):
                return node
            return exp.Cast(this=node.copy(), to=exp.DataType.build(cast_target))

        return expression.transform(_transform).sql(dialect="postgres")

    def _temporal_columns_by_name(self) -> dict[tuple[str | None, str], str]:
        columns: dict[tuple[str | None, str], str] = {}
        unqualified_targets: dict[str, set[str]] = {}

        for dataset in self.context.datasets:
            alias = str(dataset.sql_alias or "").strip().lower() or None
            for column in dataset.columns:
                cast_target = self._cast_target_for_type(column.data_type)
                if cast_target is None:
                    continue
                column_name = str(column.name or "").strip().lower()
                if not column_name:
                    continue
                columns[(alias, column_name)] = cast_target
                unqualified_targets.setdefault(column_name, set()).add(cast_target)

        if self.semantic_model is not None:
            for table_key, table in (getattr(self.semantic_model, "tables", {}) or {}).items():
                alias = str(table_key or "").strip().lower() or None
                for dimension in table.dimensions or []:
                    cast_target = self._cast_target_for_type(getattr(dimension, "type", None))
                    if cast_target is None:
                        continue
                    column_name = str(getattr(dimension, "name", "") or "").strip().lower()
                    if not column_name:
                        continue
                    columns[(alias, column_name)] = cast_target
                    unqualified_targets.setdefault(column_name, set()).add(cast_target)

        for column_name, targets in unqualified_targets.items():
            if len(targets) == 1:
                columns[(None, column_name)] = next(iter(targets))

        return columns

    @staticmethod
    def _cast_target_for_type(data_type: str | None) -> str | None:
        normalized = str(data_type or "").strip().lower()
        if not normalized:
            return None
        if normalized in {"date"}:
            return "DATE"
        if normalized in TEMPORAL_TYPE_NAMES or "timestamp" in normalized:
            return "TIMESTAMP"
        return None

    def _cast_target_for_column(
        self,
        *,
        node: exp.Column,
        temporal_columns: dict[tuple[str | None, str], str],
    ) -> str | None:
        column_name = str(node.name or "").strip().lower()
        table_name = str(node.table or "").strip().lower() or None
        if not column_name:
            return None
        return temporal_columns.get((table_name, column_name)) or temporal_columns.get((None, column_name))

    @staticmethod
    def _has_explicit_temporal_cast(node: exp.Column) -> bool:
        ancestor = node.parent
        while ancestor is not None:
            if isinstance(ancestor, (exp.Cast, exp.TryCast)):
                return True
            if isinstance(ancestor, exp.Anonymous):
                function_name = str(ancestor.name or "").strip().lower()
                if function_name in {"date", "datetime", "timestamp"}:
                    return True
            if isinstance(ancestor, (exp.Where, exp.Having, exp.Join, exp.Select, exp.Subquery)):
                return False
            ancestor = ancestor.parent
        return False

    @staticmethod
    def _is_temporal_predicate_context(node: exp.Column) -> bool:
        comparison_types = (
            exp.EQ,
            exp.NEQ,
            exp.GT,
            exp.GTE,
            exp.LT,
            exp.LTE,
            exp.Between,
            exp.Is,
            exp.In,
            exp.Like,
            exp.ILike,
        )
        boundary_types = (exp.Where, exp.Having, exp.Join, exp.Select, exp.Subquery)

        ancestor = node.parent
        while ancestor is not None:
            if isinstance(ancestor, comparison_types):
                return True
            if isinstance(ancestor, boundary_types):
                return False
            ancestor = ancestor.parent
        return False


__all__ = ["SqlAnalystTool"]
