import json
import logging
import uuid
from typing import Any, Optional

from langbridge.connectors.base import ManagedVectorDB
from langbridge.orchestrator.llm.provider.base import LLMProvider
from langbridge.runtime.embeddings import EmbeddingProvider
from langbridge.runtime.services.semantic_vector_search_service import (
    SemanticVectorSearchService,
)

from .interfaces import (
    SemanticSearchResult,
    SemanticSearchResultCollection,
    ColumnValueSearchResultCollection,
)

class SemanticSearchTool:
    def __init__(
        self,
        semantic_name: str,
        llm: LLMProvider | None = None,
        embedding_model: str | None = None,
        vector_store: ManagedVectorDB | None = None,
        entity_reconignition: bool = False,
        metadata_filters: Optional[dict] = None,
        logger: Optional[logging.Logger] = None,
        *,
        semantic_vector_search_service: SemanticVectorSearchService | None = None,
        semantic_vector_search_workspace_id: uuid.UUID | None = None,
        semantic_vector_search_model_id: uuid.UUID | None = None,
        semantic_vector_search_dataset_key: str | None = None,
        semantic_vector_search_dimension_name: str | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self._name = semantic_name
        self._llm = llm
        self._vector_store = vector_store
        self._embedding_model = embedding_model
        self._entity_recognition = entity_reconignition
        self._logger = logger or logging.getLogger(__name__)
        self._metadata_filters = metadata_filters or {}
        self._semantic_vector_search_service = semantic_vector_search_service
        self._semantic_vector_search_workspace_id = semantic_vector_search_workspace_id
        self._semantic_vector_search_model_id = semantic_vector_search_model_id
        self._semantic_vector_search_dataset_key = str(semantic_vector_search_dataset_key or "").strip() or None
        self._semantic_vector_search_dimension_name = str(semantic_vector_search_dimension_name or "").strip() or None
        self._embedding_provider = embedding_provider

        using_runtime_vector_search = self._semantic_vector_search_service is not None
        if using_runtime_vector_search:
            if self._semantic_vector_search_workspace_id is None or self._semantic_vector_search_model_id is None:
                raise ValueError(
                    "semantic_vector_search_workspace_id and semantic_vector_search_model_id are required "
                    "when semantic_vector_search_service is configured."
                )
            if not self._semantic_vector_search_dataset_key or not self._semantic_vector_search_dimension_name:
                raise ValueError(
                    "semantic_vector_search_dataset_key and semantic_vector_search_dimension_name are required "
                    "when semantic_vector_search_service is configured."
                )
        elif self._vector_store is None or self._llm is None:
            raise ValueError(
                "SemanticSearchTool requires either a runtime semantic vector search service "
                "or both llm and vector_store for legacy search."
            )
        
    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def _extract_json_blob(text: str) -> Optional[str]:
        if not text:
            return None
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    def _build_entity_prompt(self, query: str, top_k: int) -> str:
        return (
            "You extract entity phrases from a user query for vector search.\n"
            "Return STRICT JSON and nothing else.\n"
            "Schema: {\"entities\": [\"<entity>\", ...]}\n"
            "Rules:\n"
            "- Include only concrete entity values (names, ids, places, products, categories).\n"
            "- Exclude metrics, dates, time ranges, and generic nouns.\n"
            f"- Return at most {top_k} entities.\n"
            "- If none, return an empty list.\n"
            f"Query: {query}\n"
        )

    async def _extract_entity_phrases(self, query: str, top_k: int) -> list[str]:
        if self._llm is None:
            return []
        prompt = self._build_entity_prompt(query, top_k)
        try:
            response = await self._llm.acomplete(prompt, temperature=0.0, max_tokens=256)
        except Exception as exc:
            self._logger.warning("Entity recognition LLM call failed: %s", exc)
            return []
        blob = self._extract_json_blob(response) or response
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            self._logger.warning("Entity recognition response was not valid JSON: %s", response)
            return []
        if isinstance(parsed, dict):
            entities = parsed.get("entities")
        elif isinstance(parsed, list):
            entities = parsed
        else:
            entities = None
        if not isinstance(entities, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in entities:
            text = str(item or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
            if len(cleaned) >= 5:
                break
        return cleaned

    async def _search_runtime_vectors(self, query: str, top_k: int) -> SemanticSearchResultCollection:
        if self._semantic_vector_search_service is None:
            return SemanticSearchResultCollection()

        search_phrases = [query]
        if self._entity_recognition:
            candidates = await self._extract_entity_phrases(query, top_k)
            if candidates:
                search_phrases = candidates
                self._logger.info("Entity recognition phrases: %s", candidates)

        hits = await self._semantic_vector_search_service.search_dimension(
            workspace_id=self._semantic_vector_search_workspace_id,
            semantic_model_id=self._semantic_vector_search_model_id,
            dataset_key=self._semantic_vector_search_dataset_key,
            dimension_name=self._semantic_vector_search_dimension_name,
            queries=search_phrases,
            embedding_provider=self._embedding_provider,
            top_k=top_k,
        )
        results = [
            SemanticSearchResult(
                identifier=hit.index_id.int,
                score=float(hit.score),
                metadata={
                    "dataset_key": hit.dataset_key,
                    "dimension_name": hit.dimension_name,
                    "column": f"{hit.dataset_key}.{hit.dimension_name}",
                    "value": hit.matched_value,
                    "source_text": hit.source_text,
                },
            )
            for hit in hits
        ]
        return SemanticSearchResultCollection(results=results)
        
    async def search(self, query: str, top_k: int = 5) -> SemanticSearchResultCollection:
        self._logger.info(f"Performing semantic search for query: {query}")
        if top_k <= 0:
            return SemanticSearchResultCollection()

        if self._semantic_vector_search_service is not None:
            results = await self._search_runtime_vectors(query, top_k=top_k)
            self._logger.info("Found %s runtime semantic search results", len(results.results))
            return results

        search_phrases = [query]
        if self._entity_recognition:
            candidates = await self._extract_entity_phrases(query, top_k)
            if candidates:
                search_phrases = candidates
                self._logger.info("Entity recognition phrases: %s", candidates)

        embeddings = await self._llm.create_embeddings(
            search_phrases,
            embedding_model=self._embedding_model,
        )
        if not embeddings:
            self._logger.warning("No embeddings returned for query: %s", query)
            return SemanticSearchResultCollection()

        if len(embeddings) != len(search_phrases):
            self._logger.warning(
                "Embedding count mismatch: %s embeddings for %s phrases",
                len(embeddings),
                len(search_phrases),
            )

        merged: dict[int, tuple[float, dict[str, Any]]] = {}
        for embedding in embeddings:
            raw_results = await self._vector_store.search(
                embedding,
                top_k=top_k,
                metadata_filters=self._metadata_filters,
            )
            for result in raw_results:
                identifier = int(result.get("id"))
                score = float(result.get("score", 0.0))
                metadata = dict(result.get("metadata") or {})
                existing = merged.get(identifier)
                if existing is None or score > existing[0]:
                    merged[identifier] = (score, metadata)

        results = []
        for identifier, (score, metadata) in merged.items():
            results.append(
                SemanticSearchResult(
                    identifier=identifier,
                    score=float(score),
                    metadata=dict(metadata),
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        results = results[:top_k]
        self._logger.info(f"Found {len(results)} results")
        return SemanticSearchResultCollection(results=results)

    async def column_value_search(
        self,
        query: str,
        top_k: int = 5
    ) -> ColumnValueSearchResultCollection:
        self._logger.info(f"Performing column value semantic search for query: {query}")
        semantic_search_results = await self.search(query, top_k=top_k)
        return ColumnValueSearchResultCollection.from_semantic_results(semantic_search_results)
