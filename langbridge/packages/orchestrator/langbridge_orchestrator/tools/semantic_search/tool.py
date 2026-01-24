
import json
import logging
from typing import Any, Optional
from langbridge.packages.connectors.langbridge_connectors.api import ManagedVectorDB
from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider.base import LLMProvider
from .interfaces import (
    SemanticSearchResult,
    SemanticSearchResultCollection,
    ColumnValueSearchResultCollection,
)

class SemanticSearchTool:
    def __init__(
        self,
        semantic_name: str,
        llm: LLMProvider,
        embedding_model: str,
        vector_store: ManagedVectorDB,
        entity_reconignition: bool = False,
        metadata_filters: Optional[dict] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self._name = semantic_name
        self._llm = llm
        self._vector_store = vector_store
        self._embedding_model = embedding_model
        self._entity_recognition = entity_reconignition
        self._logger = logger or logging.getLogger(__name__)
        self._metadata_filters = metadata_filters or {}
        
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
        
    async def search(self, query: str, top_k: int = 5) -> SemanticSearchResultCollection:
        self._logger.info(f"Performing semantic search for query: {query}")
        if top_k <= 0:
            return SemanticSearchResultCollection()

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
