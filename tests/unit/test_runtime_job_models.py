from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from langbridge.packages.common.langbridge_common.utils.embedding_provider import (
    DEFAULT_OPENAI_EMBED_MODEL,
    EmbeddingProvider,
)
from langbridge.packages.runtime.models import (
    CreateDatasetBulkCreateJobRequest,
    CreateSqlJobRequest,
    LLMConnectionSecret,
    LLMProvider,
)


def test_create_sql_job_request_accepts_camel_case_payload() -> None:
    workspace_id = uuid.uuid4()
    request = CreateSqlJobRequest.model_validate(
        {
            "sqlJobId": str(uuid.uuid4()),
            "workspaceId": str(workspace_id),
            "userId": str(uuid.uuid4()),
            "executionMode": "federated",
            "query": "select * from orders",
            "enforcedLimit": 25,
            "enforcedTimeoutSeconds": 30,
            "allowFederation": True,
            "selectedDatasets": [
                {
                    "datasetId": str(uuid.uuid4()),
                    "alias": "Orders",
                }
            ],
        }
    )

    assert request.workspace_id == workspace_id
    assert request.workbench_mode.value == "dataset"
    assert request.selected_datasets[0].sql_alias == "orders"


def test_create_dataset_bulk_create_request_accepts_nested_camel_case_payload() -> None:
    request = CreateDatasetBulkCreateJobRequest.model_validate(
        {
            "workspaceId": str(uuid.uuid4()),
            "projectId": str(uuid.uuid4()),
            "userId": str(uuid.uuid4()),
            "connectionId": str(uuid.uuid4()),
            "selections": [
                {
                    "schema": "public",
                    "table": "orders",
                    "columns": [
                        {"name": "id", "dataType": "uuid"},
                        {"name": "created_at", "dataType": "timestamp"},
                    ],
                }
            ],
            "policyDefaults": {
                "maxPreviewRows": 100,
                "maxExportRows": 1000,
                "allowDml": False,
                "redactionRules": {"email": "mask"},
            },
        }
    )

    assert request.policy_defaults is not None
    assert request.policy_defaults.max_preview_rows == 100
    assert request.selections[0].columns[1].data_type == "timestamp"


def test_create_dataset_bulk_create_request_rejects_duplicate_columns() -> None:
    with pytest.raises(ValidationError):
        CreateDatasetBulkCreateJobRequest.model_validate(
            {
                "workspaceId": str(uuid.uuid4()),
                "userId": str(uuid.uuid4()),
                "connectionId": str(uuid.uuid4()),
                "selections": [
                    {
                        "schema": "public",
                        "table": "orders",
                        "columns": [
                            {"name": "id"},
                            {"name": "ID"},
                        ],
                    }
                ],
            }
        )


def test_embedding_provider_accepts_runtime_llm_connection_shape(monkeypatch) -> None:
    monkeypatch.setattr(EmbeddingProvider, "_build_client", lambda self: object())

    provider = EmbeddingProvider.from_llm_connection(
        LLMConnectionSecret(
            id=uuid.uuid4(),
            name="openai",
            provider=LLMProvider.OPENAI,
            model="gpt-4.1",
            api_key="secret",
        )
    )

    assert provider.provider.value == "openai"
    assert provider.embedding_model == DEFAULT_OPENAI_EMBED_MODEL
