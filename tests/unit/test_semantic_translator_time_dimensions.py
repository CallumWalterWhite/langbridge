from langbridge.packages.semantic.langbridge_semantic.model import Dimension, Measure, SemanticModel, Table
from langbridge.packages.semantic.langbridge_semantic.query import SemanticQuery, SemanticQueryEngine


def _build_orders_model() -> SemanticModel:
    return SemanticModel(
        version="1.0",
        tables={
            "orders": Table(
                schema="public",
                name="orders",
                dimensions=[Dimension(name="created_at", type="timestamp")],
                measures=[Measure(name="amount", type="number", aggregation="sum")],
            )
        },
    )


def test_measure_with_time_dimension_is_selected_and_grouped_when_no_dimensions() -> None:
    model = _build_orders_model()
    query = SemanticQuery.model_validate(
        {
            "measures": ["orders.amount"],
            "timeDimensions": [{"dimension": "public.orders.created_at", "granularity": "day"}],
        }
    )

    sql = SemanticQueryEngine().compile(query, model, dialect="postgres").sql

    assert (
        'SELECT DATE_TRUNC(\'DAY\', CAST(t0."created_at" AS TIMESTAMP)) AS "orders__created_at_day", '
        'SUM(t0."amount")'
    ) in sql
    assert 'GROUP BY DATE_TRUNC(\'DAY\', CAST(t0."created_at" AS TIMESTAMP))' in sql


def test_ordering_by_schema_table_time_dimension_uses_projected_time_dimension_alias() -> None:
    model = _build_orders_model()
    query = SemanticQuery.model_validate(
        {
            "measures": ["orders.amount"],
            "timeDimensions": [{"dimension": "public.orders.created_at", "granularity": "day"}],
            "order": [{"public.orders.created_at": "desc"}],
        }
    )

    sql = SemanticQueryEngine().compile(query, model, dialect="postgres").sql

    assert 'ORDER BY "orders__created_at_day" DESC' in sql
    assert "ORDER BY created_at DESC" not in sql


def test_relative_time_preset_builds_timestamp_window_not_literal_value_filter() -> None:
    model = _build_orders_model()
    query = SemanticQuery.model_validate(
        {
            "measures": ["orders.amount"],
            "timeDimensions": [{"dimension": "orders.created_at", "dateRange": "last_30_days"}],
        }
    )

    sql = SemanticQueryEngine().compile(query, model, dialect="postgres").sql

    assert "last_30_days" not in sql
    assert 'WHERE CAST(t0."created_at" AS TIMESTAMP) >=' in sql
    assert 'CAST(t0."created_at" AS TIMESTAMP) <' in sql


def test_custom_time_dimension_before_date_filter_builds_before_condition() -> None:
    model = _build_orders_model()
    query = SemanticQuery.model_validate(
        {
            "measures": ["orders.amount"],
            "timeDimensions": [{"dimension": "orders.created_at", "dateRange": "before:2026-01-01"}],
        }
    )

    sql = SemanticQueryEngine().compile(query, model, dialect="postgres").sql

    assert 'WHERE CAST(t0."created_at" AS TIMESTAMP) < \'2026-01-01\'' in sql


def test_custom_between_dates_uses_inclusive_day_window_for_timestamp_dimensions() -> None:
    model = _build_orders_model()
    query = SemanticQuery.model_validate(
        {
            "measures": ["orders.amount"],
            "timeDimensions": [{"dimension": "orders.created_at", "dateRange": ["2026-01-01", "2026-01-31"]}],
        }
    )

    sql = SemanticQueryEngine().compile(query, model, dialect="postgres").sql

    assert 'CAST(t0."created_at" AS TIMESTAMP) >= \'2026-01-01\'' in sql
    assert 'CAST(t0."created_at" AS TIMESTAMP) < CAST(\'2026-01-31\' AS DATE) + INTERVAL \'1 DAY\'' in sql


def test_custom_on_date_uses_casted_day_window_for_timestamp_dimensions() -> None:
    model = _build_orders_model()
    query = SemanticQuery.model_validate(
        {
            "measures": ["orders.amount"],
            "timeDimensions": [{"dimension": "orders.created_at", "dateRange": "on:2026-01-01"}],
        }
    )

    sql = SemanticQueryEngine().compile(query, model, dialect="postgres").sql

    assert 'CAST(t0."created_at" AS TIMESTAMP) >= \'2026-01-01\'' in sql
    assert 'CAST(t0."created_at" AS TIMESTAMP) < CAST(\'2026-01-01\' AS DATE) + INTERVAL \'1 DAY\'' in sql


def test_time_typed_dimension_is_cast_before_date_comparison() -> None:
    model = SemanticModel(
        version="1.0",
        tables={
            "orders": Table(
                name="orders",
                dimensions=[Dimension(name="order_date", type="time")],
                measures=[Measure(name="amount", type="number", aggregation="sum")],
            )
        },
    )
    query = SemanticQuery.model_validate(
        {
            "measures": ["orders.amount"],
            "timeDimensions": [{"dimension": "orders.order_date", "dateRange": "this_quarter"}],
        }
    )

    sql = SemanticQueryEngine().compile(query, model, dialect="postgres").sql

    assert 'CAST(t0."order_date" AS TIMESTAMP) >=' in sql
    assert 'CAST(t0."order_date" AS TIMESTAMP) <' in sql
    assert "0 + INTERVAL" not in sql


def test_measure_expression_uses_underlying_column_name_not_measure_name() -> None:
    model = SemanticModel(
        version="1.0",
        tables={
            "shopify_orders": Table(
                name="orders_enriched",
                dimensions=[Dimension(name="country", expression="country", type="string")],
                measures=[
                    Measure(
                        name="net_sales",
                        expression="net_revenue",
                        type="number",
                        aggregation="sum",
                    )
                ],
            )
        },
    )
    query = SemanticQuery.model_validate(
        {
            "measures": ["shopify_orders.net_sales"],
            "dimensions": ["shopify_orders.country"],
        }
    )

    sql = SemanticQueryEngine().compile(query, model, dialect="postgres").sql

    assert 'SUM(t0."net_revenue") AS "shopify_orders__net_sales"' in sql
    assert 'SUM(t0."net_sales")' not in sql
