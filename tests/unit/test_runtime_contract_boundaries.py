from __future__ import annotations

from pathlib import Path
import tokenize

from langbridge.contracts.base import _Base
from langbridge.contracts.datasets import DatasetListResponse
from langbridge.contracts.jobs import (
    CreateDatasetPreviewJobRequest as PackageCreateDatasetPreviewJobRequest,
    CreateSemanticQueryJobRequest as PackageCreateSemanticQueryJobRequest,
    CreateSqlJobRequest as PackageCreateSqlJobRequest,
)
from langbridge.contracts.jobs.agent_job import AgentJobStateResponse
from langbridge.contracts.jobs.dataset_job import CreateDatasetPreviewJobRequest
from langbridge.contracts.jobs.semantic_query_job import CreateSemanticQueryJobRequest
from langbridge.contracts.jobs.sql_job import CreateSqlJobRequest
from langbridge.contracts.llm_connections import LLMProvider
from langbridge.contracts.semantic import (
    SemanticQueryMetaResponse as PackageSemanticQueryMetaResponse,
    SemanticQueryRequest as PackageSemanticQueryRequest,
)
from langbridge.contracts.semantic.semantic_query import (
    SemanticQueryMetaResponse,
    SemanticQueryRequest,
)
from langbridge.contracts.sql import SqlExecuteRequest
from langbridge.contracts.threads import ThreadResponse


def test_core_runtime_services_do_not_import_removed_top_level_utils_or_errors() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_files = [
        repo_root / "langbridge/runtime/services/sql_query_service.py",
        repo_root / "langbridge/runtime/services/semantic_query_execution_service.py",
        repo_root / "langbridge/runtime/services/dataset_query_service.py",
        repo_root / "langbridge/runtime/services/dataset_sync_service.py",
        repo_root / "langbridge/runtime/services/agent_execution_service.py",
        repo_root / "langbridge/runtime/execution/federated_query_tool.py",
    ]
    forbidden_imports = ("langbridge.utils", "langbridge.errors")

    for path in runtime_files:
        source = path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            assert forbidden not in source, f"{path} still imports {forbidden}"


def test_selected_contract_modules_are_owned_by_root_langbridge_contracts_namespace() -> None:
    assert _Base.__module__ == "langbridge.contracts.base"
    assert DatasetListResponse.__module__ == "langbridge.contracts.datasets"
    assert SqlExecuteRequest.__module__ == "langbridge.contracts.sql"
    assert ThreadResponse.__module__ == "langbridge.contracts.threads"
    assert LLMProvider.__module__ == "langbridge.contracts.llm_connections"
    assert AgentJobStateResponse.__module__ == "langbridge.contracts.jobs.agent_job"
    assert CreateSqlJobRequest.__module__ == "langbridge.contracts.jobs.sql_job"
    assert CreateDatasetPreviewJobRequest.__module__ == "langbridge.contracts.jobs.dataset_job"
    assert SemanticQueryRequest.__module__ == "langbridge.contracts.semantic.semantic_query"
    assert SemanticQueryMetaResponse.__module__ == "langbridge.contracts.semantic.semantic_query"
    assert (
        CreateSemanticQueryJobRequest.__module__
        == "langbridge.contracts.jobs.semantic_query_job"
    )


def test_contract_package_exports_resolve_to_canonical_modules() -> None:
    assert PackageCreateSqlJobRequest is CreateSqlJobRequest
    assert PackageCreateDatasetPreviewJobRequest is CreateDatasetPreviewJobRequest
    assert PackageCreateSemanticQueryJobRequest is CreateSemanticQueryJobRequest
    assert PackageSemanticQueryRequest is SemanticQueryRequest
    assert PackageSemanticQueryMetaResponse is SemanticQueryMetaResponse


def test_repo_does_not_import_removed_package_contract_aliases() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    forbidden_imports = (
        "langbridge.packages.contracts.base",
        "langbridge.packages.contracts.llm_connections",
        "langbridge.packages.contracts.datasets",
        "langbridge.packages.contracts.sql",
        "langbridge.packages.contracts.threads",
        "langbridge.packages.contracts.semantic.semantic_query",
        "langbridge.packages.contracts.jobs.type",
        "langbridge.packages.contracts.jobs.agent_job",
        "langbridge.packages.contracts.jobs.sql_job",
        "langbridge.packages.contracts.jobs.dataset_job",
        "langbridge.packages.contracts.jobs.semantic_query_job",
    )

    for path in repo_root.rglob("*.py"):
        if path == Path(__file__).resolve():
            continue
        with tokenize.open(path) as handle:
            source = handle.read()
        for forbidden in forbidden_imports:
            assert forbidden not in source, f"{path} still imports {forbidden}"


def test_contract_base_keeps_alias_and_json_behavior() -> None:
    class ExamplePayload(_Base):
        example_value: int

    payload = ExamplePayload.model_validate({"exampleValue": 7})

    assert payload.example_value == 7
    assert payload.model_dump(by_alias=True) == {"exampleValue": 7}
    assert '"example_value":7' in payload.dict_json()
