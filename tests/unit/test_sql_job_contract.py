import uuid

import pytest
from pydantic import ValidationError

from langbridge.runtime.hosting.api_models import RuntimeSqlQueryRequest
from langbridge.runtime.models.jobs import (
    CreateSqlJobRequest,
    SqlWorkbenchMode,
)


def test_sql_job_contract_requires_connection_for_single_mode() -> None:
    with pytest.raises(ValidationError):
        CreateSqlJobRequest(
            sql_job_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            execution_mode="single",
            query="SELECT 1",
            enforced_limit=100,
            enforced_timeout_seconds=30,
        )


def test_sql_job_contract_requires_federated_datasets() -> None:
    with pytest.raises(ValidationError):
        CreateSqlJobRequest(
            sql_job_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            execution_mode="federated",
            query="SELECT * FROM sales.orders",
            enforced_limit=1000,
            enforced_timeout_seconds=30,
            allow_federation=True,
        )


def test_sql_job_contract_accepts_dataset_backed_federated_execution() -> None:
    dataset_id = uuid.uuid4()
    payload = CreateSqlJobRequest(
        sql_job_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        execution_mode="federated",
        query="SELECT * FROM shop.public.orders",
        enforced_limit=1000,
        enforced_timeout_seconds=30,
        allow_federation=True,
        federated_datasets=[{"alias": "shop", "dataset_id": dataset_id}],
    )

    assert payload.execution_mode == "federated"
    assert payload.workbench_mode.value == "dataset"
    assert payload.connection_id is None
    assert payload.query_dialect == "tsql"
    assert [dataset.model_dump(mode="json") for dataset in payload.selected_datasets] == [
        {
            "alias": "shop",
            "sql_alias": "shop",
            "dataset_id": str(dataset_id),
            "dataset_name": None,
            "canonical_reference": None,
            "connector_id": None,
            "source_kind": None,
            "storage_kind": None,
        }
    ]


def test_runtime_sql_query_request_accepts_direct_sql_payload() -> None:
    payload = RuntimeSqlQueryRequest(
        query="SELECT 1",
        connection_id=uuid.uuid4(),
        query_dialect="postgres",
    )

    assert payload.query == "SELECT 1"
    assert payload.query_dialect == "postgres"


def test_runtime_sql_job_defaults_to_direct_sql_workbench_mode() -> None:
    payload = CreateSqlJobRequest(
        sql_job_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        execution_mode="single",
        connection_id=uuid.uuid4(),
        query="SELECT 1",
        enforced_limit=100,
        enforced_timeout_seconds=30,
    )

    assert payload.workbench_mode == SqlWorkbenchMode.direct_sql


def test_runtime_sql_job_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        CreateSqlJobRequest(
            sql_job_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            execution_mode="single",
            connection_id=uuid.uuid4(),
            query="   ",
            enforced_limit=100,
            enforced_timeout_seconds=30,
        )
