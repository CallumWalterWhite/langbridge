"""
Supervisor orchestrator that coordinates analyst and visual agents.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from db.connector import Connector
from semantic.model import SemanticModel

from .analyst_agent import AnalystAgent, AnalystAgentConfig, AnalystAgentResultPayload
from .visual_agent import VisualAgent


@dataclass
class OrchestrationContext:
    """Context passed into the supervisor to capture routing metadata."""

    workspace_id: Optional[str]
    available_semantic_models: List[SemanticModel]
    available_connectors: List[Connector]
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

        start = time.perf_counter()

        analyst_result: AnalystAgentResultPayload = await self.analyst_agent.run(
            query=user_query,
            available_semantic_models=context.available_semantic_models,
            available_connectors=context.available_connectors,
            config=context.analyst_config,
        )

        # visualization = self.visual_agent.run(
        #     analyst_result.data,
        #     title=f"Visualization for '{user_query}'",
        # )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        self.logger.info(
            f"Orchestration completed in {elapsed_ms}ms for workspace {context.workspace_id}"
        )
        
        #print result
        self.logger.info(f"Analyst Result: {analyst_result.summary}")

        return {
            "answer": analyst_result.summary,
            "sql": analyst_result.sql,
            "data": analyst_result.data,
            # "visualization": visualization,
            "diagnostics": {
                **analyst_result.diagnostics,
                "total_elapsed_ms": elapsed_ms,
                "workspace_id": context.workspace_id,
                "trace": context.trace_metadata,
            },
        }
