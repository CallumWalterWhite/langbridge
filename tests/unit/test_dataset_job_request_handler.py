from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from langbridge.apps.worker.langbridge_worker.handlers.query.dataset_job_request_handler import (
    DatasetJobRequestHandler,
)
from langbridge.packages.common.langbridge_common.contracts.jobs.dataset_job import (
    CreateDatasetPreviewJobRequest,
)
from langbridge.packages.common.langbridge_common.contracts.jobs.type import JobType
from langbridge.packages.common.langbridge_common.db.dataset import (
    DatasetColumnRecord,
    DatasetPolicyRecord,
    DatasetRecord,
)
from langbridge.packages.common.langbridge_common.db.job import JobRecord, JobStatus
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.dataset_job import (
    DatasetJobRequestMessage,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeJobRepository:
    def __init__(self, job_record: JobRecord) -> None:
        self._job_record = job_record

    async def get_by_id(self, job_id: uuid.UUID) -> JobRecord | None:
        if job_id == self._job_record.id:
            return self._job_record
        return None


class _FakeDatasetRepository:
    def __init__(self, dataset: DatasetRecord) -> None:
        self._dataset = dataset

    async def get_for_workspace(self, *, dataset_id: uuid.UUID, workspace_id: uuid.UUID):
        if self._dataset.id == dataset_id and self._dataset.workspace_id == workspace_id:
            return self._dataset
        return None


class _FakeDatasetColumnRepository:
    def __init__(self, columns: list[DatasetColumnRecord]) -> None:
        self._columns = columns

    async def list_for_dataset(self, *, dataset_id: uuid.UUID) -> list[DatasetColumnRecord]:
        return [column for column in self._columns if column.dataset_id == dataset_id]


class _FakeDatasetPolicyRepository:
    def __init__(self, policy: DatasetPolicyRecord | None) -> None:
        self._policy = policy

    async def get_for_dataset(self, *, dataset_id: uuid.UUID):
        if self._policy is not None and self._policy.dataset_id == dataset_id:
            return self._policy
        return None

    def add(self, policy: DatasetPolicyRecord) -> None:
        self._policy = policy


class _FakeFederatedQueryTool:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def execute_federated_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self._responses:
            return self._responses.pop(0)
        return {"rows": []}


def _build_job_record(*, workspace_id: uuid.UUID, job_type: JobType) -> JobRecord:
    now = datetime.now(timezone.utc)
    return JobRecord(
        id=uuid.uuid4(),
        organisation_id=str(workspace_id),
        job_type=job_type.value,
        payload={},
        headers={},
        status=JobStatus.queued,
        progress=0,
        status_message="queued",
        created_at=now,
        queued_at=now,
        updated_at=now,
    )


@pytest.mark.anyio
async def test_dataset_preview_enforces_limit_and_applies_redaction_and_rls() -> None:
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    dataset = DatasetRecord(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=None,
        connection_id=connection_id,
        created_by=user_id,
        updated_by=user_id,
        name="orders_dataset",
        description=None,
        tags_json=["sales"],
        dataset_type="TABLE",
        dialect="tsql",
        catalog_name=None,
        schema_name="dbo",
        table_name="orders",
        sql_text=None,
        referenced_dataset_ids_json=[],
        federated_plan_json=None,
        file_config_json=None,
        status="published",
        revision_id=None,
        row_count_estimate=None,
        bytes_estimate=None,
        last_profiled_at=None,
        created_at=now,
        updated_at=now,
    )
    columns = [
        DatasetColumnRecord(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            workspace_id=workspace_id,
            name="customer_id",
            data_type="integer",
            nullable=False,
            ordinal_position=0,
            description=None,
            is_allowed=True,
            is_computed=False,
            expression=None,
            created_at=now,
            updated_at=now,
        ),
        DatasetColumnRecord(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            workspace_id=workspace_id,
            name="secret",
            data_type="text",
            nullable=True,
            ordinal_position=1,
            description=None,
            is_allowed=True,
            is_computed=False,
            expression=None,
            created_at=now,
            updated_at=now,
        ),
        DatasetColumnRecord(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            workspace_id=workspace_id,
            name="region",
            data_type="text",
            nullable=True,
            ordinal_position=2,
            description=None,
            is_allowed=True,
            is_computed=False,
            expression=None,
            created_at=now,
            updated_at=now,
        ),
    ]
    policy = DatasetPolicyRecord(
        id=uuid.uuid4(),
        dataset_id=dataset.id,
        workspace_id=workspace_id,
        max_rows_preview=10,
        max_export_rows=5000,
        redaction_rules_json={"secret": "hash"},
        row_filters_json=["region = {{region}}"],
        allow_dml=False,
        created_at=now,
        updated_at=now,
    )

    federated_tool = _FakeFederatedQueryTool(
        responses=[
            {
                "rows": [{"customer_id": 42, "secret": "cleartext", "region": "EMEA"}],
                "execution": {"total_runtime_ms": 13, "stage_metrics": [{"bytes_written": 256}]},
            }
        ]
    )
    job_record = _build_job_record(workspace_id=workspace_id, job_type=JobType.DATASET_PREVIEW)
    handler = DatasetJobRequestHandler(
        job_repository=_FakeJobRepository(job_record),
        dataset_repository=_FakeDatasetRepository(dataset),
        dataset_column_repository=_FakeDatasetColumnRepository(columns),
        dataset_policy_repository=_FakeDatasetPolicyRepository(policy),
        federated_query_tool=federated_tool,
    )
    request = CreateDatasetPreviewJobRequest(
        dataset_id=dataset.id,
        workspace_id=workspace_id,
        user_id=user_id,
        requested_limit=50,
        enforced_limit=25,
        filters={"customer_id": {"operator": "eq", "value": 42}},
        sort=[{"column": "customer_id", "direction": "desc"}],
        user_context={"region": "EMEA"},
    )
    message = DatasetJobRequestMessage(
        job_id=job_record.id,
        job_type=JobType.DATASET_PREVIEW,
        job_request=request.model_dump(mode="json"),
    )

    await handler.handle(message)

    assert job_record.status == JobStatus.succeeded
    result = (job_record.result or {}).get("result") or {}
    assert result["effective_limit"] == 10
    assert result["redaction_applied"] is True
    assert result["rows"][0]["secret"] != "cleartext"
    assert len(federated_tool.calls) == 1

    query_sql = str(result["query_sql"])
    query_upper = query_sql.upper()
    assert "REGION" in query_upper
    assert "EMEA" in query_sql
    assert ("LIMIT 10" in query_upper) or ("TOP 10" in query_upper)


@pytest.mark.anyio
async def test_dataset_sql_preview_blocks_dml_statements() -> None:
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    dataset = DatasetRecord(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=None,
        connection_id=connection_id,
        created_by=user_id,
        updated_by=user_id,
        name="unsafe_sql_dataset",
        description=None,
        tags_json=[],
        dataset_type="SQL",
        dialect="tsql",
        catalog_name=None,
        schema_name=None,
        table_name=None,
        sql_text="DELETE FROM dbo.orders",
        referenced_dataset_ids_json=[],
        federated_plan_json=None,
        file_config_json=None,
        status="published",
        revision_id=None,
        row_count_estimate=None,
        bytes_estimate=None,
        last_profiled_at=None,
        created_at=now,
        updated_at=now,
    )
    columns = [
        DatasetColumnRecord(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            workspace_id=workspace_id,
            name="order_id",
            data_type="integer",
            nullable=False,
            ordinal_position=0,
            description=None,
            is_allowed=True,
            is_computed=False,
            expression=None,
            created_at=now,
            updated_at=now,
        )
    ]
    policy = DatasetPolicyRecord(
        id=uuid.uuid4(),
        dataset_id=dataset.id,
        workspace_id=workspace_id,
        max_rows_preview=25,
        max_export_rows=5000,
        redaction_rules_json={},
        row_filters_json=[],
        allow_dml=False,
        created_at=now,
        updated_at=now,
    )
    federated_tool = _FakeFederatedQueryTool(responses=[])
    job_record = _build_job_record(workspace_id=workspace_id, job_type=JobType.DATASET_PREVIEW)
    handler = DatasetJobRequestHandler(
        job_repository=_FakeJobRepository(job_record),
        dataset_repository=_FakeDatasetRepository(dataset),
        dataset_column_repository=_FakeDatasetColumnRepository(columns),
        dataset_policy_repository=_FakeDatasetPolicyRepository(policy),
        federated_query_tool=federated_tool,
    )
    request = CreateDatasetPreviewJobRequest(
        dataset_id=dataset.id,
        workspace_id=workspace_id,
        user_id=user_id,
        enforced_limit=25,
    )
    message = DatasetJobRequestMessage(
        job_id=job_record.id,
        job_type=JobType.DATASET_PREVIEW,
        job_request=request.model_dump(mode="json"),
    )

    await handler.handle(message)

    assert job_record.status == JobStatus.failed
    error_message = str((job_record.error or {}).get("message") or "")
    assert "SELECT" in error_message.upper()
    assert federated_tool.calls == []
