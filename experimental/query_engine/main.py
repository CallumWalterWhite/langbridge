"""Example usage of the LangBridge experimental query engine."""

from __future__ import annotations

import os
import sys

try:
    from experimental.query_engine import InMemoryDataSource, QueryEngine
except ModuleNotFoundError:  # pragma: no cover - script entry point fallback
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from experimental.query_engine import InMemoryDataSource, QueryEngine


def build_example_engine() -> QueryEngine:
    """Create a query engine preloaded with example data sources."""
    engine = QueryEngine()
    engine.register_source(
        InMemoryDataSource(
            "bigquery",
            {
                "sales.customers": [
                    {"customer_id": 1, "name": "Alice"},
                    {"customer_id": 2, "name": "Bob"},
                ]
            },
        )
    )
    engine.register_source(
        InMemoryDataSource(
            "snowflake",
            {
                "analytics.orders": [
                    {"order_id": 10, "customer_id": 1, "total": 150.0},
                    {"order_id": 11, "customer_id": 1, "total": 80.0},
                    {"order_id": 12, "customer_id": 2, "total": 250.0},
                ]
            },
        )
    )
    return engine


def run_example() -> None:
    """Execute a cross-source query and print the results."""
    engine = build_example_engine()
    query = """
    SELECT c.customer_id, c.name, o.order_id, o.total
    FROM bigquery.sales.customers AS c
    JOIN snowflake.analytics.orders AS o ON o.customer_id = c.customer_id
    WHERE o.total >= 100
    """
    result = engine.execute(query)
    print("Columns:", ", ".join(result.columns))
    for row in result.rows:
        print(row)


if __name__ == "__main__":
    run_example()
