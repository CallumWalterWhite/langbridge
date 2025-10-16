"""
SQL analyst tool built on top of connector abstractions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ...connectors.base import (
    QueryResult,
    QueryValidationError,
    SchemaInfo,
    SqlConnector,
    ensure_select_statement,
)


TABLE_NAME_RE = re.compile(r"\bfrom\s+([^\s,;]+)", re.IGNORECASE)
JOIN_RE = re.compile(r"\bjoin\s+([^\s,;]+)", re.IGNORECASE)


@dataclass
class SqlGuidance:
    """
    Additional guidance for SQL generation.
    """

    goal: Optional[str] = None
    allow_tables: Optional[Sequence[str]] = None
    deny_tables: Optional[Sequence[str]] = None
    extra_instructions: Optional[str] = None
    dialect: Optional[str] = None
    max_rows: Optional[int] = 5000


class SqlAnalystTool:
    """
    Helper responsible for generating, validating and executing SQL queries.
    """

    def __init__(
        self,
        *,
        connector: SqlConnector,
        llm: Optional[BaseChatModel] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.connector = connector
        self.llm = llm
        self.logger = logger or logging.getLogger(__name__)
        self._prompt = None
        if llm:
            self._prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an analytics engineer. Convert questions into read-only SQL queries. "
                        "Use only the provided schema. Never use DML/DDL. Respond with a single SQL query.",
                    ),
                    (
                        "human",
                        "Dialect: {dialect}\nGoal: {goal}\nTables:\n{schema}\nQuestion: {question}\n"
                        "Additional instructions: {instructions}",
                    ),
                ]
            )
            self._chain = self._prompt | llm | StrOutputParser()
        else:
            self._chain = None

    # ------------------------------------------------------------------ #
    # SQL generation/validation
    # ------------------------------------------------------------------ #

    async def build_sql_from_nl(
        self,
        question: str,
        schema: SchemaInfo,
        guidance: SqlGuidance,
    ) -> str:
        if not self._chain:
            raise RuntimeError("No LLM configured for natural language to SQL generation.")

        schema_text = "\n".join(
            f"- {table.name}: {', '.join(column.name for column in table.columns)}"
            for table in schema.tables
        )
        instructions = guidance.extra_instructions or ""
        if guidance.allow_tables:
            instructions += f"\nUse only these tables: {', '.join(guidance.allow_tables)}."
        if guidance.deny_tables:
            instructions += f"\nDo not query these tables: {', '.join(guidance.deny_tables)}."

        sql = await self._chain.ainvoke(
            {
                "dialect": guidance.dialect or self.connector.dialect,
                "goal": guidance.goal or question,
                "schema": schema_text or "No tables available.",
                "question": question,
                "instructions": instructions.strip() or "Return a single SELECT statement.",
            }
        )
        return self._extract_sql(sql)

    def _extract_sql(self, raw: str) -> str:
        fenced = re.search(r"```sql\s*(.*?)```", raw, re.IGNORECASE | re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        fenced = re.search(r"```(.*?)```", raw, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return raw.strip()

    def validate_sql(self, sql: str, guidance: Optional[SqlGuidance] = None) -> None:
        ensure_select_statement(sql)
        tables = self._extract_tables(sql)
        if guidance:
            if guidance.allow_tables:
                disallowed = [t for t in tables if t not in set(guidance.allow_tables)]
                if disallowed:
                    raise QueryValidationError(f"Query references tables outside allow list: {', '.join(disallowed)}")
            if guidance.deny_tables:
                denied = [t for t in tables if t in set(guidance.deny_tables)]
                if denied:
                    raise QueryValidationError(f"Query references denied tables: {', '.join(denied)}")

    def _extract_tables(self, sql: str) -> List[str]:
        tables = TABLE_NAME_RE.findall(sql) + JOIN_RE.findall(sql)
        cleaned = [table.strip().strip("`\"") for table in tables]
        return [t for t in cleaned if t]

    async def run_sql(
        self,
        sql: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        guidance: Optional[SqlGuidance] = None,
    ) -> QueryResult:
        self.validate_sql(sql, guidance)
        result = await self.connector.execute(
            sql,
            params=params,
            max_rows=guidance.max_rows if guidance else 5000,
        )
        return result

    async def explain(self, sql: str) -> Dict[str, Any]:
        tables = self._extract_tables(sql)
        return {
            "sql": sql,
            "tables": tables,
            "dialect": self.connector.dialect,
        }

