from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

import langbridge.apps.api.langbridge_api.services.semantic.semantic_model_service as semantic_model_service_module
from langbridge.apps.api.langbridge_api.services.semantic.semantic_model_service import (
    SemanticModelService,
)
from langbridge.packages.common.langbridge_common.contracts.semantic import (
    SemanticModelCreateRequest,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _dataset_column(name: str, data_type: str, *, nullable: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        data_type=data_type,
        nullable=nullable,
        is_allowed=True,
        is_computed=False,
        expression=None,
    )


def _dataset(
    *,
    dataset_id: uuid.UUID,
    name: str,
    sql_alias: str,
    connection_id: uuid.UUID | None,
    columns: list[SimpleNamespace],
) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=dataset_id,
        workspace_id=uuid.uuid4(),
        project_id=None,
        connection_id=connection_id,
        name=name,
        sql_alias=sql_alias,
        description=f"{name} dataset",
        source_kind="database",
        storage_kind="table",
        columns=columns,
        created_at=now,
        updated_at=now,
    )


class _DatasetRepository:
    def __init__(self, datasets: list[SimpleNamespace]) -> None:
        self._datasets = {dataset.id: dataset for dataset in datasets}

    async def get_by_ids_for_workspace(
        self,
        *,
        workspace_id: uuid.UUID,
        dataset_ids: list[uuid.UUID],
    ) -> list[SimpleNamespace]:
        return [self._datasets[dataset_id] for dataset_id in dataset_ids if dataset_id in self._datasets]

    async def list_for_workspace(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> list[SimpleNamespace]:
        return list(self._datasets.values())


class _SemanticModelRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, object] = {}

    def add(self, model) -> None:
        self.items[model.id] = model

    async def flush(self) -> None:
        return None


class _LineageCaptureService:
    def __init__(self) -> None:
        self.models: list[object] = []

    async def register_semantic_model_lineage(self, *, model) -> None:
        self.models.append(model)


def _build_service(*, dataset_repository: _DatasetRepository | None = None, repository: object | None = None,
                   lineage_service: object | None = None) -> SemanticModelService:
    organization_repository = SimpleNamespace(get_by_id=lambda _organization_id: SimpleNamespace(id=_organization_id))
    project_repository = SimpleNamespace(get_by_id=lambda _project_id: None)
    return SemanticModelService(
        repository=repository or SimpleNamespace(),
        builder=SimpleNamespace(),
        organization_repository=organization_repository,
        project_repository=project_repository,
        connector_service=SimpleNamespace(),
        agent_service=SimpleNamespace(),
        semantic_search_service=SimpleNamespace(),
        emvironment_service=SimpleNamespace(),
        lineage_service=lineage_service,
        dataset_repository=dataset_repository,
    )


@pytest.mark.anyio
async def test_generate_model_yaml_from_selection_returns_dataset_first_yaml() -> None:
    organization_id = uuid.uuid4()
    orders_id = uuid.uuid4()
    customers_id = uuid.uuid4()
    connector_id = uuid.uuid4()
    service = _build_service(
        dataset_repository=_DatasetRepository(
            [
                _dataset(
                    dataset_id=orders_id,
                    name="Orders",
                    sql_alias="orders",
                    connection_id=connector_id,
                    columns=[
                        _dataset_column("id", "integer"),
                        _dataset_column("customer_id", "integer"),
                        _dataset_column("amount", "decimal"),
                    ],
                ),
                _dataset(
                    dataset_id=customers_id,
                    name="Customers",
                    sql_alias="customers",
                    connection_id=connector_id,
                    columns=[
                        _dataset_column("id", "integer"),
                        _dataset_column("region", "string"),
                    ],
                ),
            ]
        )
    )

    response = await service.generate_model_yaml_from_selection(
        organization_id=organization_id,
        selected_dataset_ids=[orders_id, customers_id],
        selected_fields={
            str(orders_id): ["id", "customer_id", "amount"],
            str(customers_id): ["id", "region"],
        },
        include_sample_values=False,
        description="Generated by test",
    )

    assert "datasets:" in response.yaml_text
    assert "orders:" in response.yaml_text
    assert "customers:" in response.yaml_text
    assert "source_dataset: orders" in response.yaml_text
    assert "target_dataset: customers" in response.yaml_text
    assert isinstance(response.warnings, list)


@pytest.mark.anyio
async def test_create_model_registers_lineage_for_dataset_backed_semantic_model(monkeypatch) -> None:
    organization_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    connector_id = uuid.uuid4()
    repository = _SemanticModelRepository()
    lineage_service = _LineageCaptureService()
    service = _build_service(
        dataset_repository=_DatasetRepository(
            [
                _dataset(
                    dataset_id=dataset_id,
                    name="Orders",
                    sql_alias="orders",
                    connection_id=connector_id,
                    columns=[
                        _dataset_column("id", "integer"),
                        _dataset_column("amount", "decimal"),
                    ],
                )
            ]
        ),
        repository=repository,
        lineage_service=lineage_service,
    )

    class _SemanticModelEntryStub:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    monkeypatch.setattr(semantic_model_service_module, "SemanticModelEntry", _SemanticModelEntryStub)

    response = await service.create_model(
        SemanticModelCreateRequest(
            connector_id=None,
            organization_id=organization_id,
            name="Orders semantic model",
            description="Maps orders dataset",
            auto_generate=True,
            source_dataset_ids=[dataset_id],
        )
    )

    assert response.id in repository.items
    assert response.source_dataset_ids == [dataset_id]
    assert len(lineage_service.models) == 1
    saved_model = lineage_service.models[0]
    assert saved_model.id == response.id
    assert '"dataset_id":' in saved_model.content_json
    assert str(dataset_id) in saved_model.content_json


@pytest.mark.anyio
async def test_create_model_uses_request_source_dataset_ids_when_yaml_omits_dataset_ids(monkeypatch) -> None:
    organization_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    connector_id = uuid.uuid4()
    repository = _SemanticModelRepository()
    service = _build_service(
        dataset_repository=_DatasetRepository(
            [
                _dataset(
                    dataset_id=dataset_id,
                    name="Orders",
                    sql_alias="orders",
                    connection_id=connector_id,
                    columns=[
                        _dataset_column("id", "integer"),
                        _dataset_column("amount", "decimal"),
                    ],
                )
            ]
        ),
        repository=repository,
    )

    class _SemanticModelEntryStub:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    monkeypatch.setattr(semantic_model_service_module, "SemanticModelEntry", _SemanticModelEntryStub)

    response = await service.create_model(
        SemanticModelCreateRequest(
            connector_id=None,
            organization_id=organization_id,
            name="Orders semantic model",
            model_yaml="""
version: '1.0'
name: Orders semantic model
datasets:
  orders:
    relation_name: orders
    dimensions:
      - name: id
        expression: id
        type: integer
        primary_key: true
""",
            auto_generate=False,
            source_dataset_ids=[dataset_id],
        )
    )

    assert response.id in repository.items
    assert repository.items[response.id].connector_id == connector_id


@pytest.mark.anyio
async def test_create_model_surfaces_clear_error_when_db_still_requires_connector_id(monkeypatch) -> None:
    organization_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    class _FailingRepository(_SemanticModelRepository):
        async def flush(self) -> None:
            raise IntegrityError(
                "insert into semantic_models",
                {},
                Exception('null value in column "connector_id" violates not-null constraint'),
            )

    repository = _FailingRepository()
    service = _build_service(
        dataset_repository=_DatasetRepository(
            [
                _dataset(
                    dataset_id=dataset_id,
                    name="Federated orders",
                    sql_alias="federated_orders",
                    connection_id=None,
                    columns=[
                        _dataset_column("id", "integer"),
                        _dataset_column("amount", "decimal"),
                    ],
                )
            ]
        ),
        repository=repository,
    )

    class _SemanticModelEntryStub:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    monkeypatch.setattr(semantic_model_service_module, "SemanticModelEntry", _SemanticModelEntryStub)

    with pytest.raises(BusinessValidationError, match="semantic_models.connector_id is still enforced as NOT NULL"):
        await service.create_model(
            SemanticModelCreateRequest(
                connector_id=None,
                organization_id=organization_id,
                name="Federated orders model",
                auto_generate=True,
                source_dataset_ids=[dataset_id],
            )
        )


@pytest.mark.anyio
async def test_get_connector_catalog_returns_dataset_catalog_items() -> None:
    organization_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    service = _build_service(
        dataset_repository=_DatasetRepository(
            [
                _dataset(
                    dataset_id=dataset_id,
                    name="Orders",
                    sql_alias="orders",
                    connection_id=None,
                    columns=[
                        _dataset_column("id", "integer"),
                        _dataset_column("amount", "decimal"),
                    ],
                )
            ]
        )
    )

    response = await service.get_connector_catalog(organization_id=organization_id)

    assert response.workspace_id == organization_id
    assert len(response.items) == 1
    assert response.items[0].id == dataset_id
    assert response.items[0].fields[0].name == "id"
