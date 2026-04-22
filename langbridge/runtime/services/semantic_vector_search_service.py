
import logging
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sqlglot
import yaml
from sqlglot import exp

from langbridge.connectors.base import ConnectorRuntimeType, get_connector_config_factory
from langbridge.connectors.base.connector import ManagedVectorDB
from langbridge.plugins.connectors import VectorDBConnectorFactory
from langbridge.runtime import settings
from langbridge.runtime.embeddings import EmbeddingProvider
from langbridge.runtime.execution.federated_query_tool import FederatedQueryTool
from langbridge.runtime.models import (
    SemanticVectorIndexMetadata,
    SemanticVectorIndexStatus,
    SemanticVectorStoreTarget,
)
from langbridge.runtime.models.llm import LLMConnectionSecret
from langbridge.runtime.ports import (
    ConnectorMetadataProvider,
    CredentialProvider,
    DatasetCatalogStore,
    DatasetMetadataProvider,
    LLMConnectionStore,
    SemanticModelMetadataProvider,
    SemanticVectorIndexStore,
)
from langbridge.runtime.services.dataset_execution import DatasetExecutionResolver
from langbridge.runtime.services.errors import ExecutionValidationError
from langbridge.semantic.loader import load_semantic_model
from langbridge.semantic.model import Dimension, SemanticModel


_INTERVAL_PART_RE = re.compile(r"(?P<count>\d+)\s*(?P<unit>[smhdw])", re.IGNORECASE)
_SAFE_INDEX_RE = re.compile(r"[^a-zA-Z0-9_]+")


@dataclass(frozen=True, slots=True)
class SemanticVectorSearchHit:
    index_id: uuid.UUID
    semantic_model_id: uuid.UUID
    dataset_key: str
    dimension_name: str
    matched_value: str
    score: float
    source_text: str


class SemanticVectorSearchService:
    @staticmethod
    def _normalize_timestamp(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def __init__(
        self,
        *,
        dataset_repository: DatasetCatalogStore | None,
        federated_query_tool: FederatedQueryTool | None,
        logger: logging.Logger,
        semantic_model_provider: SemanticModelMetadataProvider | None = None,
        semantic_vector_index_store: SemanticVectorIndexStore | None = None,
        dataset_provider: DatasetMetadataProvider | None = None,
        connector_provider: ConnectorMetadataProvider | None = None,
        credential_provider: CredentialProvider | None = None,
        llm_connection_store: LLMConnectionStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._dataset_repository = dataset_repository
        self._federated_query_tool = federated_query_tool
        self._semantic_model_provider = semantic_model_provider
        self._semantic_vector_index_store = semantic_vector_index_store
        self._dataset_provider = dataset_provider
        self._connector_provider = connector_provider
        self._credential_provider = credential_provider
        self._logger = logger
        self._embedding_provider = embedding_provider
        self._llm_connection_store = llm_connection_store
        self._vector_factory = VectorDBConnectorFactory()
        self._dataset_execution_resolver = DatasetExecutionResolver(
            dataset_repository=dataset_repository,
            dataset_provider=dataset_provider,
        )

    async def can_refresh(self) -> bool:
        return await self.refresh_unavailable_reason() is None

    async def refresh_unavailable_reason(self) -> str | None:
        if self._embedding_provider is None and self._llm_connection_store is None: # default embedding provider can be created if llm connection repository is available
            return "Semantic vector refresh requires an embedding provider."
        if self._federated_query_tool is None:
            return "Semantic vector refresh requires a federated query tool."
        if self._semantic_model_provider is None:
            return "Semantic vector refresh requires a semantic model provider."
        if self._semantic_vector_index_store is None:
            return "Semantic vector refresh requires a semantic vector index store."
        llm_connections = await self._llm_connection_store.list_llm_connections()
        if not llm_connections:
            return "At least one LLM connection is required to resolve an embedding provider for semantic vector refresh."
        return None

    async def refresh_workspace(
        self,
        *,
        workspace_id: uuid.UUID,
        embedding_provider: EmbeddingProvider | None = None,
        semantic_model_id: uuid.UUID | None = None,
        force: bool = False,
    ) -> list[SemanticVectorIndexMetadata]:
        embedder = embedding_provider or self._embedding_provider or (await self._create_embedding_provider_with_default_llm_connection())
        if embedder is None:
            raise ExecutionValidationError(
                "Semantic vector refresh requires an embedding provider."
            )
        if self._federated_query_tool is None:
            raise ExecutionValidationError(
                "Federated query tool is required for semantic vector refresh."
            )

        configured_models = await self._load_semantic_models(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
        )
        refreshed: list[SemanticVectorIndexMetadata] = []
        for model_record in configured_models:
            semantic_model = self._load_model(model_record.content_yaml)
            raw_datasets = self._extract_raw_datasets(model_record)
            synced_indexes = await self._sync_model_indexes(
                workspace_id=workspace_id,
                semantic_model_record=model_record,
                semantic_model=semantic_model,
            )
            if not synced_indexes:
                continue
            workflow, workflow_dialect = await self._dataset_execution_resolver.build_semantic_workflow(
                workspace_id=workspace_id,
                workflow_id=f"workflow_semantic_vector_{model_record.id.hex[:12]}",
                dataset_name=model_record.name or f"semantic_model_{model_record.id.hex[:8]}",
                semantic_model=semantic_model,
                raw_datasets_payload=raw_datasets,
                ignore_non_syncd_datasets=True, # avoid blocking refresh if some datasets are not yet synced, since we'll only attempt to refresh indexes for dimensions of already synced datasets
                #TODO: need to implement task dependencies and only refresh indexes for dimensions of datasets that have been synced in the same refresh run, to ensure indexes are only refreshed when their source data is ready
            )
            dimensions_by_key = {
                (dataset_key, dimension.name): dimension
                for dataset_key, dataset in semantic_model.datasets.items()
                for dimension in (dataset.dimensions or [])
                if dimension.vector and dimension.vector.enabled
            }
            for index_metadata in synced_indexes:
                if not force and not self._should_refresh(index_metadata):
                    refreshed.append(index_metadata)
                    continue
                dimension = dimensions_by_key.get(
                    (index_metadata.dataset_key, index_metadata.dimension_name)
                )
                if dimension is None:
                    continue
                refreshed.append(
                    await self._refresh_dimension_index(
                        workspace_id=workspace_id,
                        index_metadata=index_metadata,
                        workflow=workflow.model_dump(mode="json"),
                        workflow_dialect=workflow_dialect,
                        dataset_key=index_metadata.dataset_key,
                        dimension=dimension,
                        embedding_provider=embedder,
                    )
                )
        return refreshed

    async def search(
        self,
        *,
        workspace_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        queries: Sequence[str],
        embedding_provider: EmbeddingProvider | None = None,
        top_k: int = 5,
    ) -> list[SemanticVectorSearchHit]:
        return await self._search_index_records(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
            queries=queries,
            embedding_provider=embedding_provider,
            top_k=top_k,
            dataset_key=None,
            dimension_name=None,
            max_hits_per_index=1,
        )

    async def search_dimension(
        self,
        *,
        workspace_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        dataset_key: str,
        dimension_name: str,
        queries: Sequence[str],
        embedding_provider: EmbeddingProvider | None = None,
        top_k: int = 5,
    ) -> list[SemanticVectorSearchHit]:
        return await self._search_index_records(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
            queries=queries,
            embedding_provider=embedding_provider,
            top_k=top_k,
            dataset_key=dataset_key,
            dimension_name=dimension_name,
            max_hits_per_index=max(1, int(top_k)),
        )

    async def _search_index_records(
        self,
        *,
        workspace_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        queries: Sequence[str],
        embedding_provider: EmbeddingProvider | None = None,
        top_k: int,
        dataset_key: str | None,
        dimension_name: str | None,
        max_hits_per_index: int,
    ) -> list[SemanticVectorSearchHit]:
        embedder = embedding_provider or self._embedding_provider or (await self._create_embedding_provider_with_default_llm_connection())
        if embedder is None or top_k <= 0:
            return []

        await self._sync_indexes_for_search(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
        )
        index_records = await self._list_ready_indexes(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
        )
        if dataset_key is not None:
            index_records = [record for record in index_records if record.dataset_key == dataset_key]
        if dimension_name is not None:
            index_records = [record for record in index_records if record.dimension_name == dimension_name]
        if not index_records:
            return []

        cleaned_queries = [
            str(query).strip()
            for query in queries
            if isinstance(query, str) and str(query).strip()
        ]
        if not cleaned_queries:
            return []

        embeddings = await embedder.embed(cleaned_queries)
        if not embeddings:
            return []

        hits: list[SemanticVectorSearchHit] = []
        for record in index_records:
            try:
                vector_store = await self._resolve_vector_store(
                    workspace_id=workspace_id,
                    index_metadata=record,
                )
            except Exception as exc:
                self._logger.warning(
                    "Unable to open semantic vector index %s for search: %s",
                    record.id,
                    exc,
                )
                continue

            hits_by_match_key: dict[str, SemanticVectorSearchHit] = {}
            for query_text, embedding in zip(cleaned_queries, embeddings):
                try:
                    search_results = await vector_store.search(
                        embedding,
                        top_k=max(1, int(max_hits_per_index)),
                    )
                except Exception as exc:
                    self._logger.warning(
                        "Semantic vector search failed for index %s: %s",
                        record.id,
                        exc,
                    )
                    break
                if not search_results:
                    continue
                for result in search_results:
                    metadata = dict(result.get("metadata") or {})
                    matched_value = str(metadata.get("value") or "").strip()
                    if not matched_value:
                        continue
                    candidate = SemanticVectorSearchHit(
                        index_id=record.id,
                        semantic_model_id=record.semantic_model_id,
                        dataset_key=record.dataset_key,
                        dimension_name=record.dimension_name,
                        matched_value=matched_value,
                        score=float(result.get("score") or 0.0),
                        source_text=query_text,
                    )
                    match_key = str(result.get("id") or matched_value).strip().lower()
                    prior = hits_by_match_key.get(match_key)
                    if prior is None or candidate.score > prior.score:
                        hits_by_match_key[match_key] = candidate
            hits.extend(
                sorted(
                    hits_by_match_key.values(),
                    key=lambda item: item.score,
                    reverse=True,
                )[: max(1, int(max_hits_per_index))]
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    async def _sync_indexes_for_search(
        self,
        *,
        workspace_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
    ) -> None:
        configured_models = await self._load_semantic_models(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
        )
        for model_record in configured_models:
            semantic_model = self._load_model(model_record.content_yaml)
            await self._sync_model_indexes(
                workspace_id=workspace_id,
                semantic_model_record=model_record,
                semantic_model=semantic_model,
            )

    async def _sync_model_indexes(
        self,
        *,
        workspace_id: uuid.UUID,
        semantic_model_record: Any,
        semantic_model: SemanticModel,
    ) -> list[SemanticVectorIndexMetadata]:
        store = self._require_vector_index_store()
        existing = await store.list_for_workspace(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_record.id,
        )
        existing_by_key = {
            (item.dataset_key, item.dimension_name): item
            for item in existing
        }

        desired_keys: set[tuple[str, str]] = set()
        synced: list[SemanticVectorIndexMetadata] = []
        for dataset_key, dataset in semantic_model.datasets.items():
            for dimension in dataset.dimensions or []:
                if not dimension.vector or not dimension.vector.enabled:
                    continue
                desired_key = (dataset_key, dimension.name)
                if desired_key in desired_keys:
                    self._logger.warning(
                        "Skipping duplicate semantic vector index definition for %s.%s in semantic model %s.",
                        dataset_key,
                        dimension.name,
                        semantic_model_record.id,
                    )
                    continue
                desired_keys.add(desired_key)
                prior = existing_by_key.get(desired_key)
                candidate = await self._build_index_metadata(
                    workspace_id=workspace_id,
                    semantic_model_id=semantic_model_record.id,
                    dataset_key=dataset_key,
                    dimension=dimension,
                    prior=prior,
                )
                saved = await store.save(candidate)
                existing_by_key[desired_key] = saved
                synced.append(saved)

        for stale in existing:
            if (stale.dataset_key, stale.dimension_name) in desired_keys:
                continue
            await self._delete_index_metadata(
                workspace_id=workspace_id,
                index_metadata=stale,
            )
        return synced

    async def _build_index_metadata(
        self,
        *,
        workspace_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        dataset_key: str,
        dimension: Dimension,
        prior: SemanticVectorIndexMetadata | None,
    ) -> SemanticVectorIndexMetadata:
        vector_config = dimension.vector
        if vector_config is None or not vector_config.enabled:
            raise ExecutionValidationError("Vector index metadata can only be built for enabled dimensions.")

        store_target = SemanticVectorStoreTarget(vector_config.store.type)
        connector_name = vector_config.store.connector_name
        connector_id = None
        if store_target == SemanticVectorStoreTarget.CONNECTOR:
            connector_id = await self._resolve_connector_id(
                workspace_id=workspace_id,
                connector_name=connector_name,
            )
            if connector_id is None:
                raise ExecutionValidationError(
                    f"Semantic vector dimension '{dataset_key}.{dimension.name}' references "
                    f"unknown vector connector '{connector_name}'."
                )

        vector_index_name = self._build_index_name(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
            dataset_key=dataset_key,
            dimension_name=dimension.name,
            configured_name=vector_config.store.index_name,
        )
        refresh_interval_seconds = self._parse_refresh_interval(
            vector_config.refresh_interval
        )
        now = datetime.now(timezone.utc)

        if prior is not None:
            reset_state = (
                prior.vector_store_target != store_target
                or prior.vector_connector_name != connector_name
                or prior.vector_connector_id != connector_id
                or prior.vector_index_name != vector_index_name
                or prior.refresh_interval_seconds != refresh_interval_seconds
            )
            updates: dict[str, Any] = {
                "dataset_key": dataset_key,
                "dimension_name": dimension.name,
                "vector_store_target": store_target,
                "vector_connector_name": connector_name,
                "vector_connector_id": connector_id,
                "vector_index_name": vector_index_name,
                "refresh_interval_seconds": refresh_interval_seconds,
                "updated_at": now,
            }
            if reset_state:
                updates.update(
                    {
                        "refresh_status": SemanticVectorIndexStatus.PENDING,
                        "indexed_value_count": None,
                        "embedding_dimension": None,
                        "last_refresh_started_at": None,
                        "last_refreshed_at": None,
                        "last_refresh_error": None,
                    }
                )
            return prior.model_copy(update=updates)

        return SemanticVectorIndexMetadata(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
            dataset_key=dataset_key,
            dimension_name=dimension.name,
            vector_store_target=store_target,
            vector_connector_name=connector_name,
            vector_connector_id=connector_id,
            vector_index_name=vector_index_name,
            refresh_interval_seconds=refresh_interval_seconds,
            refresh_status=SemanticVectorIndexStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    async def _delete_index_metadata(
        self,
        *,
        workspace_id: uuid.UUID,
        index_metadata: SemanticVectorIndexMetadata,
    ) -> None:
        store = self._require_vector_index_store()
        try:
            vector_store = await self._resolve_vector_store(
                workspace_id=workspace_id,
                index_metadata=index_metadata,
            )
        except Exception:
            vector_store = None
        if vector_store is not None:
            try:
                await vector_store.delete_index()
            except Exception:
                self._logger.debug(
                    "Unable to delete obsolete semantic vector index %s",
                    index_metadata.id,
                    exc_info=True,
                )
        await store.delete(
            workspace_id=workspace_id,
            semantic_vector_index_id=index_metadata.id,
        )

    async def _refresh_dimension_index(
        self,
        *,
        workspace_id: uuid.UUID,
        index_metadata: SemanticVectorIndexMetadata,
        workflow: dict[str, Any],
        workflow_dialect: str,
        dataset_key: str,
        dimension: Dimension,
        embedding_provider: EmbeddingProvider,
    ) -> SemanticVectorIndexMetadata:
        store = self._require_vector_index_store()
        in_progress = index_metadata.model_copy(
            update={
                "refresh_status": SemanticVectorIndexStatus.REFRESHING,
                "last_refresh_started_at": datetime.now(timezone.utc),
                "last_refresh_error": None,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        saved_state = await store.save(in_progress)

        try:
            distinct_values = await self._fetch_distinct_values(
                workspace_id=workspace_id,
                workflow=workflow,
                workflow_dialect=workflow_dialect,
                dataset_key=dataset_key,
                dimension=dimension,
                max_values=getattr(dimension.vector, "max_values", None),
            )
            embeddings = await embedding_provider.embed(distinct_values)
            if embeddings and len(embeddings) != len(distinct_values):
                raise ExecutionValidationError(
                    "Embedding count mismatch while refreshing semantic vector index."
                )

            vector_store = await self._resolve_vector_store(
                workspace_id=workspace_id,
                index_metadata=saved_state,
            )
            await self._reset_vector_store(
                vector_store=vector_store,
                embeddings=embeddings,
                values=distinct_values,
            )

            refreshed_at = datetime.now(timezone.utc)
            return await store.save(
                saved_state.model_copy(
                    update={
                        "refresh_status": SemanticVectorIndexStatus.READY,
                        "indexed_value_count": len(distinct_values),
                        "embedding_dimension": (
                            len(embeddings[0]) if embeddings else None
                        ),
                        "last_refreshed_at": refreshed_at,
                        "last_refresh_error": None,
                        "updated_at": refreshed_at,
                    }
                )
            )
        except Exception as exc:
            self._logger.warning(
                "Semantic vector refresh failed for %s.%s: %s",
                index_metadata.dataset_key,
                index_metadata.dimension_name,
                exc,
            )
            failed_at = datetime.now(timezone.utc)
            return await store.save(
                saved_state.model_copy(
                    update={
                        "refresh_status": SemanticVectorIndexStatus.FAILED,
                        "last_refresh_error": str(exc),
                        "updated_at": failed_at,
                    }
                )
            )

    async def _fetch_distinct_values(
        self,
        *,
        workspace_id: uuid.UUID,
        workflow: dict[str, Any],
        workflow_dialect: str,
        dataset_key: str,
        dimension: Dimension,
        max_values: int | None,
    ) -> list[str]:
        if self._federated_query_tool is None:
            raise ExecutionValidationError(
                "Federated query tool is required for semantic vector refresh."
            )

        query_sql = self._build_distinct_query(
            dataset_key=dataset_key,
            dimension=dimension,
            dialect=workflow_dialect,
            max_values=max_values,
        )
        execution = await self._federated_query_tool.execute_federated_query(
            {
                "workspace_id": str(workspace_id),
                "query": query_sql,
                "dialect": workflow_dialect,
                "workflow": workflow,
            }
        )
        rows_payload = execution.get("rows") or []
        values: list[str] = []
        seen: set[str] = set()
        for row in rows_payload:
            if isinstance(row, Mapping):
                raw_value = row.get("value")
                if raw_value is None and row:
                    raw_value = next(iter(row.values()))
            elif isinstance(row, (list, tuple)):
                raw_value = row[0] if row else None
            else:
                raw_value = row
            normalized = str(raw_value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            values.append(normalized)
        values.sort()
        return values

    def _build_distinct_query(
        self,
        *,
        dataset_key: str,
        dimension: Dimension,
        dialect: str,
        max_values: int | None,
    ) -> str:
        expression_sql = str(dimension.expression or dimension.name).strip()
        if not expression_sql:
            raise ExecutionValidationError(
                f"Dimension '{dimension.name}' is missing an expression."
            )
        try:
            expression = sqlglot.parse_one(expression_sql, read=dialect)
        except sqlglot.ParseError:
            expression = exp.Column(this=exp.Identifier(this=dimension.name, quoted=True))

        query = (
            exp.select(exp.alias_(expression.copy(), "value", quoted=True))
            .distinct()
            .from_(exp.table_(dataset_key, quoted=False))
            .where(
                exp.Not(
                    this=exp.Is(this=expression.copy(), expression=exp.Null())
                )
            )
        )
        if max_values is not None and max_values > 0:
            query = query.limit(max_values)
        return query.sql(dialect=dialect)

    async def _reset_vector_store(
        self,
        *,
        vector_store: ManagedVectorDB,
        embeddings: Sequence[Sequence[float]],
        values: Sequence[str],
    ) -> None:
        try:
            await vector_store.delete_index()
        except Exception:
            self._logger.debug("Semantic vector store delete skipped.", exc_info=True)

        if not embeddings:
            return

        await vector_store.create_index(len(embeddings[0]))
        await vector_store.upsert_vectors(
            embeddings,
            metadata=[{"value": value} for value in values],
        )

    async def _resolve_vector_store(
        self,
        *,
        workspace_id: uuid.UUID,
        index_metadata: SemanticVectorIndexMetadata,
    ) -> ManagedVectorDB:
        target = SemanticVectorStoreTarget(index_metadata.vector_store_target)
        if target == SemanticVectorStoreTarget.MANAGED_FAISS:
            connector_class = self._vector_factory.get_managed_vector_db_class_reference(
                ConnectorRuntimeType.FAISS
            )
            return await connector_class.create_managed_instance(
                {"index_name": index_metadata.vector_index_name, "location": settings.runtime_settings.MANAGED_VECTOR_FAISS_DB_DIR},
                logger=self._logger,
            )

        connector = await self._load_connector_for_index(
            workspace_id=workspace_id,
            index_metadata=index_metadata,
        )
        if connector.connector_type is None:
            raise ValueError(
                f"Connector '{connector.id}' does not define a connector_type."
            )
        connector_type = connector.connector_type
        connector_class = self._vector_factory.get_managed_vector_db_class_reference(
            connector_type
        )
        connector_payload = self._resolve_connector_config(connector)
        runtime_config = dict(connector_payload.get("config") or {})
        runtime_config = self._apply_index_namespace(
            connector_type=connector_type,
            runtime_config=runtime_config,
            index_name=index_metadata.vector_index_name,
        )
        config_factory = get_connector_config_factory(connector_type)
        config_instance = config_factory.create(runtime_config)
        return connector_class(config=config_instance, logger=self._logger)

    async def _load_connector_for_index(
        self,
        *,
        workspace_id: uuid.UUID,
        index_metadata: SemanticVectorIndexMetadata,
    ) -> Any:
        if index_metadata.vector_connector_id is None:
            raise ExecutionValidationError(
                f"Semantic vector index '{index_metadata.id}' is missing a vector connector."
            )
        if self._connector_provider is None:
            raise ExecutionValidationError(
                "Connector metadata provider is required for explicit semantic vector connectors."
            )
        connector = await self._connector_provider.get_connector(
            workspace_id=workspace_id,
            connector_id=index_metadata.vector_connector_id,
        )
        if connector is None:
            raise ExecutionValidationError(
                f"Vector connector '{index_metadata.vector_connector_name or index_metadata.vector_connector_id}' was not found."
            )
        return connector

    async def _resolve_connector_id(
        self,
        *,
        workspace_id: uuid.UUID,
        connector_name: str | None,
    ) -> uuid.UUID | None:
        normalized_name = str(connector_name or "").strip()
        if not normalized_name:
            return None
        if self._connector_provider is None:
            raise ExecutionValidationError(
                "Connector metadata provider is required for explicit semantic vector connectors."
            )
        connector = await self._connector_provider.get_connector_by_name(
            workspace_id=workspace_id,
            connector_name=normalized_name,
        )
        if connector is None:
            return None
        return connector.id

    def _resolve_connector_config(self, connector: Any) -> dict[str, Any]:
        resolved_payload = dict(getattr(connector, "config", None) or {})
        runtime_config = dict(resolved_payload.get("config") or {})

        connection_metadata = getattr(connector, "connection_metadata", None)
        if connection_metadata is not None:
            metadata = connection_metadata.model_dump(exclude_none=True, by_alias=True)
            extra = metadata.pop("extra", {})
            for key, value in metadata.items():
                runtime_config.setdefault(key, value)
            if isinstance(extra, dict):
                for key, value in extra.items():
                    if value is not None:
                        runtime_config.setdefault(key, value)

        if self._credential_provider is not None:
            for secret_name, secret_ref in dict(
                getattr(connector, "secret_references", None) or {}
            ).items():
                runtime_config[secret_name] = self._credential_provider.resolve_secret(
                    secret_ref
                )

        resolved_payload["config"] = runtime_config
        return resolved_payload

    @staticmethod
    def _apply_index_namespace(
        *,
        connector_type: ConnectorRuntimeType,
        runtime_config: dict[str, Any],
        index_name: str,
    ) -> dict[str, Any]:
        updated = dict(runtime_config)
        if connector_type == ConnectorRuntimeType.QDRANT:
            updated["collection"] = index_name
            return updated
        if connector_type == ConnectorRuntimeType.FAISS:
            configured_location = str(updated.get("location") or "~/langbridge/faiss_data").strip()
            location_path = Path(configured_location).expanduser()
            base_directory = location_path.parent if location_path.suffix else location_path
            updated["location"] = str(base_directory / index_name)
            return updated
        return updated

    async def _load_semantic_models(
        self,
        *,
        workspace_id: uuid.UUID,
        semantic_model_id: uuid.UUID | None,
    ) -> list[Any]:
        if self._semantic_model_provider is None:
            raise ExecutionValidationError(
                "Semantic model provider is required for semantic vector search."
            )
        if semantic_model_id is not None:
            model = await self._semantic_model_provider.get_semantic_model(
                workspace_id=workspace_id,
                semantic_model_id=semantic_model_id,
            )
            return [model] if model is not None else []
        return await self._semantic_model_provider.get_semantic_models(
            workspace_id=workspace_id,
            semantic_model_ids=None,
        )

    async def _list_ready_indexes(
        self,
        *,
        workspace_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
    ) -> list[SemanticVectorIndexMetadata]:
        store = self._require_vector_index_store()
        indexes = await store.list_for_workspace(
            workspace_id=workspace_id,
            semantic_model_id=semantic_model_id,
        )
        return [
            index
            for index in indexes
            if index.refresh_status == SemanticVectorIndexStatus.READY
            and index.last_refreshed_at is not None
            and int(index.indexed_value_count or 0) > 0
        ]
        
    async def _create_embedding_provider_with_default_llm_connection(
        self
    ):
        if self._llm_connection_store is None:
            raise ExecutionValidationError(
                "LLM connection repository is required to resolve default LLM connection for embedding provider."
            )
        
        llm_connections: list[LLMConnectionSecret] = await self._llm_connection_store.list_llm_connections()
        if not llm_connections:
            raise ExecutionValidationError(
                "No LLM connections are available to resolve default embedding provider."
            )
        
        default_connection = next((conn for conn in llm_connections if conn.default), None)
        if default_connection is None:
            raise ExecutionValidationError(
                "No default LLM connection is configured to resolve default embedding provider."
            )
            
        return EmbeddingProvider.from_llm_connection(default_connection)
            

    @staticmethod
    def _load_model(content_yaml: str) -> SemanticModel:
        return load_semantic_model(content_yaml)

    @staticmethod
    def _extract_raw_datasets(model_record: Any) -> Mapping[str, Any] | None:
        payload: Any = None
        content_json = getattr(model_record, "content_json", None)
        if isinstance(content_json, dict):
            payload = content_json
        elif isinstance(content_json, str) and content_json.strip():
            try:
                payload = yaml.safe_load(content_json)
            except Exception:
                payload = None
        if payload is None:
            try:
                payload = yaml.safe_load(getattr(model_record, "content_yaml", "") or "")
            except Exception:
                payload = None
        if not isinstance(payload, Mapping):
            return None
        datasets = payload.get("datasets")
        if isinstance(datasets, Mapping):
            return datasets
        tables = payload.get("tables")
        if isinstance(tables, Mapping):
            return tables
        return None

    @staticmethod
    def _build_index_name(
        *,
        workspace_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        dataset_key: str,
        dimension_name: str,
        configured_name: str | None,
    ) -> str:
        candidate = str(configured_name or "").strip()
        if not candidate:
            candidate = (
                f"semantic_{workspace_id.hex[:8]}_{semantic_model_id.hex[:8]}_"
                f"{dataset_key}_{dimension_name}"
            )
        candidate = _SAFE_INDEX_RE.sub("_", candidate).strip("_").lower()
        return candidate or f"semantic_{semantic_model_id.hex[:12]}"

    @staticmethod
    def _parse_refresh_interval(value: str | None) -> int | None:
        normalized = str(value or "").strip().lower()
        if not normalized:
            return None
        total_seconds = 0
        consumed = ""
        for match in _INTERVAL_PART_RE.finditer(normalized):
            count = int(match.group("count"))
            unit = match.group("unit").lower()
            consumed += match.group(0)
            if unit == "s":
                total_seconds += count
            elif unit == "m":
                total_seconds += count * 60
            elif unit == "h":
                total_seconds += count * 3600
            elif unit == "d":
                total_seconds += count * 86400
            elif unit == "w":
                total_seconds += count * 604800
        if total_seconds <= 0 or normalized.replace(" ", "") != consumed.replace(" ", ""):
            raise ExecutionValidationError(
                f"Invalid semantic vector refresh interval '{value}'."
            )
        return total_seconds

    @staticmethod
    def _should_refresh(index_metadata: SemanticVectorIndexMetadata) -> bool:
        last_refreshed_at = SemanticVectorSearchService._normalize_timestamp(
            index_metadata.last_refreshed_at
        )
        if last_refreshed_at is None:
            return True
        interval_seconds = index_metadata.refresh_interval_seconds
        if interval_seconds is None or interval_seconds <= 0:
            return False
        return datetime.now(timezone.utc) >= (
            last_refreshed_at + timedelta(seconds=interval_seconds)
        )

    def _require_vector_index_store(self) -> SemanticVectorIndexStore:
        if self._semantic_vector_index_store is None:
            raise ExecutionValidationError(
                "Semantic vector index store is required for semantic vector search."
            )
        return self._semantic_vector_index_store


SemanticSearchRefreshService = SemanticVectorSearchService
