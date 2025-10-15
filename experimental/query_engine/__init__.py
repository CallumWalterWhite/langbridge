"""LangBridge experimental query engine package.

This package provides a lightweight SQL-inspired language that allows LangBridge
users to compose analytical queries spanning multiple heterogeneous data sources
(for example BigQuery and Snowflake). Queries are parsed into a logical plan,
the required data slices are retrieved from each source, and results are joined
and evaluated in memory.

Example
-------
>>> from experimental.query_engine import QueryEngine, InMemoryDataSource
>>> engine = QueryEngine()
>>> engine.register_source(InMemoryDataSource(
...     "warehouse",
...     {"analytics.customers": [{"id": 1, "name": "Alice"}]},
... ))
>>> engine.execute(
...     "SELECT c.id, c.name "
...     "FROM warehouse.analytics.customers AS c"
... )
QueryResult(columns=['id', 'name'], rows=[(1, 'Alice')])
"""

from .datasource import (
    BigQueryDataSource,
    DataSource,
    DataSourceRegistry,
    InMemoryDataSource,
    RawTable,
    SnowflakeDataSource,
    SQLQueryRunnerDataSource,
    TableHandle,
)
from .engine import QueryEngine, QueryResult
from .exceptions import (
    ParseError,
    QueryEngineError,
    QueryExecutionError,
    QueryPlanningError,
)
from .executor import QueryExecutor, TableData
from .model import (
    ColumnRef,
    JoinClause,
    Literal,
    Predicate,
    PredicateOperand,
    SelectItem,
    SelectQuery,
    TableReference,
    Wildcard,
)
from .parser import QueryParser, Token, tokenize
from .planner import FilterNode, JoinNode, PlanNode, ProjectionNode, QueryPlanner, ScanNode

__all__ = [
    "BigQueryDataSource",
    "ColumnRef",
    "DataSource",
    "DataSourceRegistry",
    "FilterNode",
    "InMemoryDataSource",
    "JoinClause",
    "JoinNode",
    "Literal",
    "ParseError",
    "PlanNode",
    "Predicate",
    "PredicateOperand",
    "ProjectionNode",
    "QueryEngine",
    "QueryEngineError",
    "QueryExecutionError",
    "QueryExecutor",
    "QueryPlanningError",
    "QueryParser",
    "QueryResult",
    "QueryPlanner",
    "RawTable",
    "SQLQueryRunnerDataSource",
    "ScanNode",
    "SelectItem",
    "SelectQuery",
    "SnowflakeDataSource",
    "TableData",
    "TableHandle",
    "TableReference",
    "Token",
    "Wildcard",
    "tokenize",
]
