from types import SimpleNamespace

import pytest

from langbridge.apps.worker.langbridge_worker.handlers.jobs.agentic_semantic_model_job_request_handler import (
    AgenticSemanticModelJobRequestHandler,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
)
from langbridge.packages.semantic.langbridge_semantic.loader import load_semantic_model


def _build_handler() -> AgenticSemanticModelJobRequestHandler:
    return AgenticSemanticModelJobRequestHandler(
        job_repository=SimpleNamespace(),
        semantic_model_repository=SimpleNamespace(),
        dataset_repository=SimpleNamespace(),
        llm_repository=SimpleNamespace(),
        message_broker=SimpleNamespace(),
    )


def _dataset_blueprints():
    return [
        {
            "dataset": SimpleNamespace(id="orders-id", name="Orders", description="Orders dataset", connection_id=None),
            "dataset_id": "orders-id",
            "dataset_key": "orders",
            "dataset_name": "Orders",
            "columns": [
                SimpleNamespace(name="id", data_type="integer"),
                SimpleNamespace(name="customer_id", data_type="integer"),
                SimpleNamespace(name="amount", data_type="decimal"),
            ],
            "field_names": {"id", "customer_id", "amount"},
        },
        {
            "dataset": SimpleNamespace(
                id="customers-id",
                name="Customers",
                description="Customers dataset",
                connection_id=None,
            ),
            "dataset_id": "customers-id",
            "dataset_key": "customers",
            "dataset_name": "Customers",
            "columns": [
                SimpleNamespace(name="id", data_type="integer"),
                SimpleNamespace(name="region", data_type="string"),
            ],
            "field_names": {"id", "region"},
        },
    ]


def test_agentic_handler_builds_valid_yaml_from_dataset_blueprints() -> None:
    handler = _build_handler()
    blueprints = _dataset_blueprints()

    payload, warnings = handler._build_payload_from_dataset_blueprints(
        dataset_blueprints=blueprints,
        question_prompts=["revenue by region", "top customers", "monthly trend"],
    )
    yaml_text = handler._render_and_validate_yaml(payload, blueprints)
    parsed = load_semantic_model(yaml_text)

    assert "orders" in parsed.datasets
    assert "customers" in parsed.datasets
    assert parsed.relationships is not None
    assert len(parsed.relationships) == 1
    assert parsed.relationships[0].source_dataset == "orders"
    assert parsed.relationships[0].target_dataset == "customers"
    assert isinstance(warnings, list)


def test_agentic_handler_rejects_mismatched_column_mapping() -> None:
    handler = _build_handler()
    blueprints = _dataset_blueprints()
    payload, _ = handler._build_payload_from_dataset_blueprints(
        dataset_blueprints=blueprints,
        question_prompts=["revenue by region", "top customers", "monthly trend"],
    )

    # Drop one selected column from generated payload to force validation failure.
    dimensions = payload["datasets"]["orders"]["dimensions"]
    payload["datasets"]["orders"]["dimensions"] = [
        dimension for dimension in dimensions if dimension["name"] != "customer_id"
    ]

    with pytest.raises(BusinessValidationError):
        handler._render_and_validate_yaml(payload, blueprints)


def test_agentic_handler_normalizes_duplicate_relationship_names() -> None:
    handler = _build_handler()
    blueprints = _dataset_blueprints()
    payload, _ = handler._build_payload_from_dataset_blueprints(
        dataset_blueprints=blueprints,
        question_prompts=["revenue by region", "top customers", "monthly trend"],
    )

    payload["relationships"] = [
        {
            "name": "orders_to_customers",
            "source_dataset": "orders",
            "source_field": "customer_id",
            "target_dataset": "customers",
            "target_field": "id",
            "operator": "=",
            "type": "many_to_one",
        },
        {
            "name": "orders_to_customers",
            "source_dataset": "orders",
            "source_field": "id",
            "target_dataset": "customers",
            "target_field": "id",
            "operator": "=",
            "type": "many_to_one",
        },
    ]

    yaml_text = handler._render_and_validate_yaml(payload, blueprints)
    parsed = load_semantic_model(yaml_text)

    relationship_names = [relationship.name for relationship in parsed.relationships or []]
    assert len(relationship_names) == len(set(relationship_names))
    assert relationship_names == ["orders_to_customers", "orders_to_customers_2"]
