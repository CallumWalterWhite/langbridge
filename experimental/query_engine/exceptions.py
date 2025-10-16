"""Exception hierarchy for the LangBridge experimental query engine."""




class QueryEngineError(RuntimeError):
    """Base exception for query engine errors."""


class ParseError(QueryEngineError, ValueError):
    """Raised when the query language parser encounters an invalid statement."""


class QueryPlanningError(QueryEngineError):
    """Raised when the planner cannot construct an execution plan."""


class QueryExecutionError(QueryEngineError):
    """Raised when execution fails."""


__all__ = [
    "ParseError",
    "QueryEngineError",
    "QueryPlanningError",
    "QueryExecutionError",
]
