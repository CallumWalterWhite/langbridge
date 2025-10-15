"""High-level facade for the LangBridge experimental query engine."""

from __future__ import annotations

from .datasource import DataSource, DataSourceRegistry, InMemoryDataSource
from .exceptions import QueryEngineError
from .executor import QueryExecutor, QueryResult
from .parser import QueryParser
from .planner import QueryPlanner


class QueryEngine:
    """Facade for parsing, planning, and executing LangBridge queries."""

    def __init__(self):
        self._registry = DataSourceRegistry()

    def register_source(self, source: DataSource) -> None:
        """Register a new data source by name."""
        if not isinstance(source, DataSource):
            raise QueryEngineError(
                f"Source {source!r} does not implement the DataSource protocol"
            )
        self._registry.register(source)

    def execute(self, query: str) -> QueryResult:
        """Parse, plan, and execute the supplied query."""
        parsed_query = QueryParser.parse(query)
        plan = QueryPlanner(self._registry).plan(parsed_query)
        executor = QueryExecutor(self._registry)
        return executor.execute(plan)


__all__ = [
    "QueryEngine",
    "QueryResult",
    "InMemoryDataSource",
]
