from __future__ import annotations

import uuid

from langbridge.packages.federation.models import FederationWorkflow, VirtualDataset, VirtualTableBinding
from langbridge.packages.federation.models.plans import StageType
from langbridge.packages.federation.planner import FederatedPlanner


def _workflow() -> FederationWorkflow:
    workspace = str(uuid.uuid4())
    return FederationWorkflow(
        id="wf-opt",
        workspace_id=workspace,
        dataset=VirtualDataset(
            id="ds-opt",
            name="optimizer",
            workspace_id=workspace,
            tables={
                "orders": VirtualTableBinding(
                    table_key="orders",
                    source_id="source_orders",
                    connector_id=uuid.uuid4(),
                    schema="dbo",
                    table="orders",
                ),
                "customers": VirtualTableBinding(
                    table_key="customers",
                    source_id="source_customers",
                    connector_id=uuid.uuid4(),
                    schema="dbo",
                    table="customers",
                ),
            },
        ),
    )


def test_optimizer_pushes_projection_and_filter() -> None:
    planner = FederatedPlanner()
    workflow = _workflow()

    sql = (
        "SELECT o.customer_id, c.name "
        "FROM dbo.orders o "
        "JOIN dbo.customers c ON o.customer_id = c.id "
        "WHERE o.amount > 100"
    )

    output = planner.plan_sql(
        sql=sql,
        dialect="tsql",
        workflow=workflow,
        source_dialects={"source_orders": "postgres", "source_customers": "snowflake"},
    )

    scan_stages = {
        stage.subplan.alias: stage.subplan
        for stage in output.physical_plan.stages
        if stage.stage_type == StageType.REMOTE_SCAN and stage.subplan is not None
    }

    orders_subplan = scan_stages["o"]
    customers_subplan = scan_stages["c"]

    assert "amount" in orders_subplan.projected_columns
    assert "customer_id" in orders_subplan.projected_columns
    assert any("amount" in predicate for predicate in orders_subplan.pushed_filters)

    assert "name" in customers_subplan.projected_columns
    assert "id" in customers_subplan.projected_columns


def test_optimizer_avoids_full_query_pushdown_for_synthetic_catalog_bindings() -> None:
    planner = FederatedPlanner()
    workspace = str(uuid.uuid4())
    workflow = FederationWorkflow(
        id="wf-opt-synthetic-catalog",
        workspace_id=workspace,
        dataset=VirtualDataset(
            id="ds-opt-synthetic-catalog",
            name="optimizer synthetic catalog",
            workspace_id=workspace,
            tables={
                "orders": VirtualTableBinding(
                    table_key="orders",
                    source_id="source_orders",
                    connector_id=uuid.uuid4(),
                    schema="dbo",
                    table="orders",
                    catalog="org_abc__src_123",
                    metadata={
                        "physical_catalog": None,
                        "physical_schema": "dbo",
                        "physical_table": "orders",
                        "skip_catalog_in_pushdown": True,
                    },
                ),
            },
        ),
    )

    sql = 'SELECT o.id FROM "org_abc__src_123"."dbo"."orders" o WHERE o.id > 10'
    output = planner.plan_sql(
        sql=sql,
        dialect="tsql",
        workflow=workflow,
        source_dialects={"source_orders": "postgres"},
    )

    stage_ids = {stage.stage_id for stage in output.physical_plan.stages}
    assert "scan_full_query" not in stage_ids
    scan_stage = next(
        stage for stage in output.physical_plan.stages if stage.stage_type == StageType.REMOTE_SCAN
    )
    assert scan_stage.subplan is not None
    assert "org_abc__src_123" not in scan_stage.subplan.sql
