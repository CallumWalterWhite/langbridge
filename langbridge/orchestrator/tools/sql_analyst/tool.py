"""
LangChain tool surface for the SQL analyst.
"""
from typing import Any, Optional

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain.tools import BaseTool

from .llm_adapter import LangChainLLMAdapter
from .schemas import SQLAnalystToolInput, SQLAnalystToolResult
from .service import SQLAnalystService, create_service


class SQLAnalystTool(BaseTool):
    """
    LangChain tool that exposes SQL synthesis capabilities.
    """

    name = "sql_analyst"
    description = (
        "Translate a natural language analytics question into SQL using a semantic model YAML definition."
    )
    args_schema = SQLAnalystToolInput

    def __init__(self, service: SQLAnalystService):
        super().__init__()
        self._service = service

    def _run(
        self,
        question: str,
        semantic_model_yaml: str,
        dialect: Optional[str] = None,
        model_name: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **_: Any,
    ) -> str:
        result = self._service.generate_sql(
            question,
            semantic_model_yaml,
            dialect=dialect,
            model_name=model_name,
        )
        return result.sql

    async def _arun(
        self,
        question: str,
        semantic_model_yaml: str,
        dialect: Optional[str] = None,
        model_name: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **_: Any,
    ) -> str:
        result = await self._service.agenerate_sql(
            question,
            semantic_model_yaml,
            dialect=dialect,
            model_name=model_name,
        )
        return result.sql

    def run_structured(self, tool_input: SQLAnalystToolInput) -> SQLAnalystToolResult:
        """
        Provide a structured invocation entry-point.
        """

        return self._service.generate_sql(
            tool_input.question,
            tool_input.semantic_model_yaml,
            dialect=tool_input.dialect,
            model_name=tool_input.model_name,
        )

    async def arun_structured(self, tool_input: SQLAnalystToolInput) -> SQLAnalystToolResult:
        return await self._service.agenerate_sql(
            tool_input.question,
            tool_input.semantic_model_yaml,
            dialect=tool_input.dialect,
            model_name=tool_input.model_name,
        )


def create_langchain_tool(runnable) -> SQLAnalystTool:
    """
    Convenience helper that constructs the tool from any LangChain runnable.
    """

    service = create_service(LangChainLLMAdapter(runnable))
    return SQLAnalystTool(service)


__all__ = ["SQLAnalystTool", "create_langchain_tool"]
