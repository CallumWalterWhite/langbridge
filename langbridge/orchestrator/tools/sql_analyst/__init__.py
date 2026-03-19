"""
Public API for dataset-first federated analytical tooling.
"""

from .interfaces import (
    AnalyticalColumn,
    AnalyticalContext,
    AnalyticalDatasetBinding,
    AnalyticalField,
    AnalyticalMetric,
    AnalystQueryRequest,
    AnalystQueryResponse,
    QueryResult,
    SemanticModel,
)
from .semantic_loader import SemanticModelError, load_semantic_model
from .tool import SqlAnalystTool

__all__ = [
    "AnalyticalColumn",
    "AnalyticalContext",
    "AnalyticalDatasetBinding",
    "AnalyticalField",
    "AnalyticalMetric",
    "AnalystQueryRequest",
    "AnalystQueryResponse",
    "QueryResult",
    "SemanticModel",
    "SqlAnalystTool",
    "SemanticModelError",
    "load_semantic_model",
]
