from pathlib import Path
from typing import Any, Optional

import sqlite3
import yaml

from demo_sqlite import create_demo_db
from model import SemanticModel
from translator import TsqlSemanticTranslator


SKIP_SQLITE_TOKENS = ("GETDATE()", "DATEADD(", "DATEDIFF(")


def _load_model() -> SemanticModel:
    model_path = Path(__file__).with_name("sample_semantic_model.yml")
    model_payload = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    return SemanticModel.model_validate(model_payload)


def _should_execute_sqlite(sql: str) -> bool:
    return not any(token in sql for token in SKIP_SQLITE_TOKENS)


def _try_parse_sql(sql: str, sqlglot: Optional[Any]) -> bool:
    if not sqlglot:
        return True
    try:
        sqlglot.parse_one(sql, read="tsql")
        return True
    except Exception as exc:
        print(f"SQL parse failed: {exc}")
        return False


def _try_execute_sqlite(sql: str, sqlglot: Optional[Any], db_path: Path) -> None:
    if not sqlglot:
        print("SQLite execution skipped: sqlglot is not available.")
        return
    if not _should_execute_sqlite(sql):
        print("SQLite execution skipped: query uses T-SQL date functions.")
        return
    try:
        sqlite_sql = sqlglot.transpile(sql, read="tsql", write="sqlite")[0]
    except Exception as exc:
        print(f"SQLite execution skipped: unable to transpile T-SQL ({exc}).")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(sqlite_sql)
        rows = cursor.fetchmany(5)
        columns = [col[0] for col in (cursor.description or [])]
        print("SQLite columns:", columns)
        print("SQLite rows:")
        for row in rows:
            print(row)
        conn.close()
    except sqlite3.Error as exc:
        print(f"SQLite execution skipped: {exc}")


def run_demo() -> None:
    db_path = create_demo_db()
    model = _load_model()
    translator = TsqlSemanticTranslator()

    try:
        import sqlglot
    except Exception:
        sqlglot = None

    cases = [
        {
            "name": "Revenue by region and order month",
            "query": {
                "measures": ["total_revenue"],
                "dimensions": ["customers.region"],
                "timeDimensions": [
                    {
                        "dimension": "orders.order_date",
                        "granularity": "month",
                        "dateRange": ["2023-06-01", "2023-12-31"],
                    }
                ],
                "segments": ["orders.completed_only"],
                "filters": [
                    {"member": "products.category", "operator": "equals", "values": ["Electronics"]},
                ],
                "order": [{"total_revenue": "desc"}, {"orders.order_date.month": "asc"}],
                "limit": 5,
            },
        },
        {
            "name": "Channel performance with regional filters",
            "query": {
                "measures": ["avg_order_value", "orders_count"],
                "dimensions": ["orders.channel", "customers.region"],
                "filters": [
                    {"member": "orders.status", "operator": "notEquals", "values": ["cancelled"]},
                    {"member": "customers.region", "operator": "in", "values": ["North", "South"]},
                ],
                "order": {"avg_order_value": "desc"},
                "limit": 10,
            },
        },
        {
            "name": "High value categories with HAVING filters",
            "query": {
                "measures": ["total_revenue", "order_items.quantity"],
                "dimensions": ["products.category"],
                "filters": [
                    {"member": "orders.status", "operator": "equals", "values": ["completed"]},
                    {"member": "total_revenue", "operator": "gt", "values": ["500"]},
                ],
                "order": [{"total_revenue": "desc"}, {"products.category": "asc"}],
                "limit": 5,
            },
        },
        {
            "name": "Units sold by product and channel with date range",
            "query": {
                "measures": ["order_items.quantity"],
                "dimensions": ["products.name", "orders.channel"],
                "timeDimensions": [
                    {
                        "dimension": "orders.order_date",
                        "dateRange": ["2023-07-01", "2023-10-31"],
                    }
                ],
                "segments": ["products.electronics_only"],
                "order": {"order_items.quantity": "desc"},
                "limit": 5,
                "offset": 2,
            },
        },
        {
            "name": "Customer search with time filter",
            "query": {
                "measures": ["orders_count"],
                "dimensions": ["customers.name", "customers.region"],
                "filters": [
                    {"member": "customers.name", "operator": "contains", "values": ["1"]},
                    {
                        "timeDimension": "customers.signup_date",
                        "operator": "inDateRange",
                        "values": ["2023-01-01", "2023-12-31"],
                    },
                ],
                "order": {"orders_count": "desc"},
                "limit": 5,
            },
        },
    ]

    failures = []
    for case in cases:
        name = case["name"]
        print(f"\n=== {name} ===\n")
        try:
            sql = translator.translate(case["query"], model)
        except Exception as exc:
            print(f"Translation failed: {exc}")
            failures.append(name)
            continue

        print(sql)
        if not _try_parse_sql(sql, sqlglot):
            failures.append(name)
            continue

        _try_execute_sqlite(sql, sqlglot, db_path)

    if failures:
        print("\nFailures:", ", ".join(failures))
    else:
        print("\nAll queries translated successfully.")


if __name__ == "__main__":
    run_demo()
