"""
Analyst agent that selects between multiple SQL analyst tools.
"""
import logging
from typing import Any, Optional, Sequence

from orchestrator.tools.sql_analyst.interfaces import AnalystQueryRequest, AnalystQueryResponse
from orchestrator.tools.sql_analyst.tool import SqlAnalystTool
from .selector import SemanticToolSelector


class AnalystAgent:
    """
    Orchestrates NL-to-SQL workflow by delegating to the most relevant SqlAnalystTool.
    """

    def __init__(
        self,
        tools: Sequence[SqlAnalystTool],
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not tools:
            raise ValueError("AnalystAgent requires at least one SqlAnalystTool.")
        self._tools = list(tools)
        self.selector = SemanticToolSelector(self._tools)
        self.logger = logger or logging.getLogger(__name__)

    def answer(
        self,
        question: str,
        *,
        filters: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> AnalystQueryResponse:
        """
        Route a natural language question to the most suitable SQL analyst tool.
        """

        request = AnalystQueryRequest(
            question=question,
            filters=filters,
            limit=limit if limit is not None else 1000,
        )
        return self.answer_with_request(request)

    def answer_with_request(self, request: AnalystQueryRequest) -> AnalystQueryResponse:
        tool = self.selector.select(request)
        self.logger.info("AnalystAgent selected semantic model '%s'", tool.name)
        return tool.run(request)

    async def answer_async(
        self,
        question: str,
        *,
        filters: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> AnalystQueryResponse:
        request = AnalystQueryRequest(
            question=question,
            filters=filters,
            limit=limit if limit is not None else 1000,
        )
        tool = self.selector.select(request)
        self.logger.info("AnalystAgent selected semantic model '%s'", tool.name)
        return await tool.arun(request)


__all__ = ["AnalystAgent"]
