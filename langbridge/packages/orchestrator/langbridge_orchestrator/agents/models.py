from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from langbridge.packages.orchestrator.langbridge_orchestrator.agents.deep_research.agent import DeepResearchResult
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.web_search.agent import WebSearchResult
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.sql_analyst.interfaces import AnalystQueryResponse


@dataclass
class PlanExecutionArtifacts:
    """Intermediate artefacts captured while executing a planner-generated workflow."""

    analyst_result: Optional[AnalystQueryResponse] = None
    data_payload: Dict[str, Any] = field(default_factory=dict)
    visualization: Dict[str, Any] = field(default_factory=dict)
    research_result: Optional[DeepResearchResult] = None
    web_search_result: Optional[WebSearchResult] = None
    clarifying_question: Optional[str] = None
    tool_calls: list[Dict[str, Any]] = field(default_factory=list)