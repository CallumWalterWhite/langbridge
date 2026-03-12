try:  # pragma: no cover - optional deps for analyst stack can be missing in lightweight environments
    from .analyst import AnalystAgent, AnalyticalContextSelector, ToolSelectionError
except Exception:  # pragma: no cover
    AnalystAgent = None
    AnalyticalContextSelector = None
    ToolSelectionError = None

try:  # pragma: no cover
    from .bi_copilot import BICopilotAgent
except Exception:  # pragma: no cover
    BICopilotAgent = None

try:  # pragma: no cover
    from .deep_research import DeepResearchAgent, DeepResearchFinding, DeepResearchResult
except Exception:  # pragma: no cover
    DeepResearchAgent = None
    DeepResearchFinding = None
    DeepResearchResult = None

try:  # pragma: no cover
    from .web_search import (
        DuckDuckGoInstantAnswerProvider,
        WebSearchAgent,
        WebSearchProvider,
        WebSearchResult,
        WebSearchResultItem,
    )
except Exception:  # pragma: no cover
    DuckDuckGoInstantAnswerProvider = None
    WebSearchAgent = None
    WebSearchProvider = None
    WebSearchResult = None
    WebSearchResultItem = None
from .planner import (
    PlanningAgent,
    PlannerRequest,
    PlanningConstraints,
    Plan,
    PlanStep,
    RouteName,
)
try:  # pragma: no cover
    from .supervisor import OrchestrationContext, SupervisorOrchestrator
except Exception:  # pragma: no cover
    OrchestrationContext = None
    SupervisorOrchestrator = None
try:
    from .visual import VisualAgent, VisualizationSpec
except ImportError:  # pragma: no cover - optional dependency
    VisualAgent = None
    VisualizationSpec = None

__all__ = [
    "AnalystAgent",
    "AnalyticalContextSelector",
    "ToolSelectionError",
    "BICopilotAgent",
    "DeepResearchAgent",
    "DeepResearchFinding",
    "DeepResearchResult",
    "DuckDuckGoInstantAnswerProvider",
    "WebSearchAgent",
    "WebSearchProvider",
    "WebSearchResult",
    "WebSearchResultItem",
    "VisualAgent",
    "VisualizationSpec",
    "OrchestrationContext",
    "SupervisorOrchestrator",
    "PlanningAgent",
    "PlannerRequest",
    "PlanningConstraints",
    "Plan",
    "PlanStep",
    "RouteName",
]
