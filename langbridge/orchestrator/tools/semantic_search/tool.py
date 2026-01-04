
import logging
from typing import Optional
from connectors import ManagedVectorDB
from orchestrator.llm.provider.base import LLMProvider

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
        
    async def search(self, query: str, top_k: int = 5):
        self._logger.info(f"Performing semantic search for query: {query}")
        results = await self._vector_store.search(query, top_k=top_k, metadata_filters=self._metadata_filters)
        self._logger.info(f"Found {len(results)} results")
        return results