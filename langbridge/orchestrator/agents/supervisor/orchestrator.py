"""
Supervisor orchestrator that coordinates analyst and visual agents.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from orchestrator.tools.sql_analyst.interfaces import AnalystQueryResponse
from orchestrator.agents.analyst import AnalystAgent
from orchestrator.agents.visual import VisualAgent

@dataclass
class OrchestrationContext:
    """Context passed into the supervisor to capture routing metadata."""

    analyst_tools: Sequence[Any]  # Retained for backwards compatibility / auditing
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

    async def handle(
        self,
        user_query: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute analyst + visualization workflow for a single user query."""

        start = time.perf_counter()

        analyst_result: AnalystQueryResponse = await self.analyst_agent.answer_async(
            user_query,
            filters=filters,
            limit=limit,
        )

        data_payload = {}
        if analyst_result.result:
            data_payload = {
                "columns": analyst_result.result.columns,
                "rows": analyst_result.result.rows,
            }

        visualization = self.visual_agent.run(
            data_payload or {"columns": [], "rows": []},
            title=title or f"Visualization for '{user_query}'",
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        self.logger.info(
            "Orchestration completed in %sms for query '%s'", elapsed_ms, user_query
        )

        return {
            "sql_canonical": analyst_result.sql_canonical,
            "sql_executable": analyst_result.sql_executable,
            "dialect": analyst_result.dialect,
            "model": analyst_result.model_name,
            "result": data_payload,
            "visualization": visualization,
            "diagnostics": {
                "execution_time_ms": analyst_result.execution_time_ms,
                "total_elapsed_ms": elapsed_ms,
                "error": analyst_result.error,
                "dialect": analyst_result.dialect,
            },
        }


__all__ = ["OrchestrationContext", "SupervisorOrchestrator"]

