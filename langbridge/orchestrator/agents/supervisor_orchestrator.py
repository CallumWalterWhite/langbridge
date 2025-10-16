"""
Supervisor orchestrator that coordinates analyst and visual agents.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .analyst_agent import AnalystAgent, AnalystAgentConfig, AnalystAgentResultPayload
from .visual_agent import VisualAgent
from ...connectors.registry import DataSource


@dataclass
class OrchestrationContext:
    """Context passed into the supervisor to capture routing metadata."""

    workspace_id: Optional[str]
    datasource: DataSource
    analyst_config: Optional[AnalystAgentConfig] = None
    trace_metadata: Dict[str, Any] = field(default_factory=dict)


class SupervisorOrchestrator:
    """High-level orchestrator routing between analyst and visual agents."""

    def __init__(
        self,
        *,
        analyst_agent: AnalystAgent,
        visual_agent: VisualAgent,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.analyst_agent = analyst_agent
        self.visual_agent = visual_agent
        self.logger = logger or logging.getLogger(__name__)

    async def handle(self, user_query: str, context: OrchestrationContext) -> Dict[str, Any]:
        """Execute analyst + visualization workflow for a single user query."""

        self.logger.info(
            "SupervisorOrchestrator.handle start workspace=%s datasource=%s",
            context.workspace_id,
            context.datasource.id,
        )
        start = time.perf_counter()

        analyst_result: AnalystAgentResultPayload = await self.analyst_agent.run(
            query=user_query,
            datasource=context.datasource,
            config=context.analyst_config,
        )

        visualization = self.visual_agent.run(
            analyst_result.data,
            title=f"Visualization for '{user_query}'",
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return {
            "answer": analyst_result.summary,
            "sql": analyst_result.sql,
            "data": analyst_result.data,
            "visualization": visualization,
            "diagnostics": {
                **analyst_result.diagnostics,
                "total_elapsed_ms": elapsed_ms,
                "workspace_id": context.workspace_id,
                "datasource_id": context.datasource.id,
                "trace": context.trace_metadata,
            },
        }


if __name__ == "__main__":  # pragma: no cover - demonstration only
    import asyncio
    from typing import Dict, Optional, Sequence

    from langchain_community.llms.fake import FakeListLLM

    from ...connectors.base import ColumnSchema, SchemaInfo, SqlConnector, TableSchema
    from ...connectors.registry import ConnectorRegistry, VaultProtocol


    class DemoVault(VaultProtocol):
        async def get_secret(self, secret_ref: str) -> Dict[str, Any]:
            return {}


    class FakeConnector(SqlConnector):
        def __init__(self) -> None:
            super().__init__(name="fake", dialect="generic")

        async def _execute_select(self, sql: str, params: Dict[str, Any], *, timeout_s: Optional[int]):
            columns = ["month", "revenue"]
            rows = [["2024-01", 12000], ["2024-02", 18000]]
            return columns, rows

        async def _fetch_schema(self, tables: Optional[Sequence[str]]):
            table = TableSchema(
                name="sales",
                columns=[
                    ColumnSchema(name="month", type="TEXT"),
                    ColumnSchema(name="revenue", type="NUMERIC"),
                ],
            )
            return SchemaInfo(tables=[table])


    registry = ConnectorRegistry(vault=DemoVault(), logger=logging.getLogger("demo"))
    registry.register("fake", lambda ds, secrets: FakeConnector())
    datasource = DataSource(id="fake-ds", type="fake", config={}, secret_ref=None)

    fake_llm = FakeListLLM(responses=["```sql\nSELECT month, revenue FROM sales\n```"])
    analyst_agent = AnalystAgent(registry=registry, llm=fake_llm)
    visual_agent = VisualAgent()
    orchestrator = SupervisorOrchestrator(analyst_agent=analyst_agent, visual_agent=visual_agent)

    result = asyncio.run(
        orchestrator.handle(
            "What is the monthly revenue?",
            OrchestrationContext(workspace_id="demo", datasource=datasource),
        )
    )
    print(json.dumps(result, indent=2))
