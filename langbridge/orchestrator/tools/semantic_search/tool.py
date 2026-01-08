
import logging
from typing import Optional
from connectors import ManagedVectorDB
from orchestrator.llm.provider.base import LLMProvider
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
        vector_store: ManagedVectorDB,
        metadata_filters: Optional[dict] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self._name = semantic_name
        self._llm = llm
        self._vector_store = vector_store
        self._logger = logger or logging.getLogger(__name__)
        self._metadata_filters = metadata_filters or {}
        
    @property
    def name(self) -> str:
        return self._name
        
    async def search(self, query: str, top_k: int = 5) -> SemanticSearchResultCollection:
        self._logger.info(f"Performing semantic search for query: {query}")
        embeddings = await self._llm.create_embeddings([query])
        if not embeddings:
            self._logger.warning("No embeddings returned for query: %s", query)
            return SemanticSearchResultCollection()
        query_embedding = embeddings[0]
        raw_results = await self._vector_store.search(
            query_embedding,
            top_k=top_k,
            metadata_filters=self._metadata_filters,
        )
        results = [
            SemanticSearchResult(
                identifier=int(result.get("id")),
                score=float(result.get("score", 0.0)),
                metadata=result.get("metadata") or {},
            )
            for result in raw_results
        ]
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
