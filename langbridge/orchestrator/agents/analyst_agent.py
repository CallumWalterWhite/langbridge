"""
Analyst agent that orchestrates NL->SQL generation using connector abstractions.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from connectors.base import QueryResult, SchemaInfo, SqlConnector
from connectors.registry import ConnectorRegistry, DataSource
from .sql_tool import SqlAnalystTool, SqlGuidance


@dataclass
class AnalystAgentConfig:
    """
    Configuration for AnalystAgent runtime constraints.
    """

    max_rows: int = 5000
    timeout_s: int = 30
    allow_tables: Optional[list[str]] = None
    deny_tables: Optional[list[str]] = None
    goal: Optional[str] = None
    extra_instructions: Optional[str] = None


@dataclass
class AnalystAgentResultPayload:
    summary: str
    sql: str
    data: Dict[str, Any]
    diagnostics: Dict[str, Any]


class AnalystAgent:
    """
    Coordinated agent responsible for generating, validating, executing analytical SQL.
    """

    def __init__(
        self,
        *,
        registry: ConnectorRegistry,
        llm: Optional[BaseChatModel],
        summarizer: Optional[BaseChatModel] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.registry = registry
        self.llm = llm
        self.summarizer = summarizer
        self.logger = logger or logging.getLogger(__name__)
        self._tool_cache: Dict[str, SqlAnalystTool] = {}
        self._connector_cache: Dict[str, SqlConnector] = {}
        self._schema_cache: Dict[str, SchemaInfo] = {}
        self._summary_chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an analytics expert. Summarise SQL results for business stakeholders.",
                    ),
                    ("human", "Question: {question}\nSQL: {sql}\nPreview: {preview}"),
                ]
            )
            | summarizer
            | StrOutputParser()
            if summarizer
            else None
        )

    async def _get_connector(self, datasource: DataSource) -> SqlConnector:
        if datasource.id in self._connector_cache:
            return self._connector_cache[datasource.id]
        connector = await self.registry.get_for_datasource(datasource)
        self._connector_cache[datasource.id] = connector
        return connector

    async def _get_tool(self, datasource: DataSource) -> SqlAnalystTool:
        if datasource.id in self._tool_cache:
            return self._tool_cache[datasource.id]
        connector = await self._get_connector(datasource)
        tool = SqlAnalystTool(connector=connector, llm=self.llm, logger=self.logger)
        self._tool_cache[datasource.id] = tool
        return tool

    async def _get_schema(self, datasource: DataSource) -> SchemaInfo:
        if datasource.id in self._schema_cache:
            return self._schema_cache[datasource.id]
        connector = await self._get_connector(datasource)
        schema = await connector.get_schema()
        self._schema_cache[datasource.id] = schema
        return schema

    async def _generate_summary(
        self,
        question: str,
        sql: str,
        result: QueryResult,
    ) -> str:
        if not self._summary_chain:
            return f"Retrieved {result.rowcount} rows across {len(result.columns)} columns."
        preview_rows = result.rows[: min(len(result.rows), 5)]
        preview = {"columns": result.columns, "rows": preview_rows}
        return await self._summary_chain.ainvoke(
            {"question": question, "sql": sql, "preview": preview}
        )

    async def run(
        self,
        *,
        query: str,
        datasource: DataSource,
        config: Optional[AnalystAgentConfig] = None,
        params: Optional[Dict[str, Any]] = None,
        is_sql: bool = False,
    ) -> AnalystAgentResultPayload:
        """
        Execute the full NL -> SQL -> execution pipeline.
        """

        config = config or AnalystAgentConfig()
        tool = await self._get_tool(datasource)
        schema = await self._get_schema(datasource)

        guidance = SqlGuidance(
            goal=config.goal or query,
            allow_tables=config.allow_tables,
            deny_tables=config.deny_tables,
            extra_instructions=config.extra_instructions,
            dialect=tool.connector.dialect,
            max_rows=config.max_rows,
        )

        if not is_sql:
            if self.llm is None:
                raise RuntimeError("No LLM configured to translate natural language queries.")
            sql = await tool.build_sql_from_nl(query, schema, guidance)
        else:
            sql = query

        tool.validate_sql(sql, guidance)

        start = time.perf_counter()
        result = await tool.run_sql(sql, params=params, guidance=guidance)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        summary = await self._generate_summary(query, sql, result)

        payload = AnalystAgentResultPayload(
            summary=summary.strip(),
            sql=sql,
            data=result.json_safe(),
            diagnostics={
                "elapsed_ms": elapsed_ms,
                "rowcount": result.rowcount,
                "dialect": tool.connector.dialect,
            },
        )
        return payload
