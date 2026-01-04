"""
Analyst agent that selects between multiple SQL analyst tools.
"""
import asyncio
import logging
from typing import Any, Optional, Sequence

from orchestrator.llm.provider import LLMProvider
from orchestrator.tools.sql_analyst.interfaces import AnalystQueryRequest, AnalystQueryResponse
from orchestrator.tools.sql_analyst.tool import SqlAnalystTool
from orchestrator.tools.semantic_search import SemanticSearchTool
from .selector import SemanticToolSelector


class AnalystAgent:
    """
    Orchestrates NL-to-SQL workflow by delegating to the most relevant SqlAnalystTool.
    """

    def __init__(
        self,
        llm: LLMProvider,
        search_tools: Sequence[SemanticSearchTool],
        sql_tools: Sequence[SqlAnalystTool],
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.llm = llm
        self._search_tools = list(search_tools)
        self._sql_tools = list(sql_tools)
        if not self._sql_tools:
            raise ValueError("At least one SqlAnalystTool must be provided to AnalystAgent.")
        self.selector = SemanticToolSelector(self.llm, self._sql_tools)
        self.logger = logger or logging.getLogger(__name__)

    def answer(
        self,
        question: str,
        *,
        conversation_context: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> AnalystQueryResponse:
        """
        Route a natural language question to the most suitable SQL analyst tool.
        """

        request = AnalystQueryRequest(
            question=question,
            conversation_context=conversation_context,
            filters=filters,
            limit=limit if limit is not None else 1000,
        )
        return self.answer_with_request(request)
    
    def search_semantically(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Perform semantic search across all available search tools.
        """
        results = {}
        for tool in self._search_tools:
            tool_results = asyncio.run(tool.search(query, top_k=top_k))
            results[tool.name] = tool_results
        return results
    
    async def search_semantically_async(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Perform semantic search across all available search tools asynchronously.
        """
        results = {}
        for tool in self._search_tools:
            tool_results = await tool.search(query, top_k=top_k)
            results[tool.name] = tool_results
        return results

    def answer_with_request(self, request: AnalystQueryRequest) -> AnalystQueryResponse:
        tool = self.selector.select(request)
        self.logger.info("AnalystAgent selected semantic model '%s'", tool.name)
        semantic_search_results = {}
        if self._search_tools:
            semantic_search_results = self.search_semantically(
                query=request.question,
                top_k=5,
            )
            request.semantic_search_results = semantic_search_results
        return tool.run(request)
        
    async def answer_async(
        self,
        question: str,
        *,
        conversation_context: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> AnalystQueryResponse:
        request = AnalystQueryRequest(
            question=question,
            conversation_context=conversation_context,
            filters=filters,
            limit=limit if limit is not None else 1000,
        )
        tool = await asyncio.to_thread(self.selector.select, request)
        self.logger.info("AnalystAgent selected semantic model '%s'", tool.name)
        semantic_search_results = {}
        if self._search_tools:
            semantic_search_results = await self.search_semantically_async(
                query=request.question,
                top_k=5,
            )
            request.semantic_search_results = semantic_search_results
        return await tool.arun(request)


__all__ = ["AnalystAgent"]
