import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import langbridge.apps.api.langbridge_api.services.dashboard_service as dashboard_service_module
from langbridge.apps.api.langbridge_api.services.dashboard_service import DashboardService
from langbridge.packages.common.langbridge_common.contracts.dashboards import (
    DashboardCreateRequest,
    DashboardSnapshotUpsertRequest,
    DashboardUpdateRequest,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
)


class FakeDashboard:
    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_service():
    repository = SimpleNamespace(
        add=MagicMock(),
        delete=AsyncMock(),
        list_for_scope=AsyncMock(return_value=[]),
        get_for_scope=AsyncMock(return_value=None),
    )
    organization_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    project_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    semantic_model_service = SimpleNamespace(get_model=AsyncMock(return_value=None))
    snapshot_storage = SimpleNamespace(
        read_snapshot=AsyncMock(return_value=None),
        write_snapshot=AsyncMock(return_value="org/dashboard.json"),
        delete_snapshot=AsyncMock(),
    )

    service = DashboardService(
        repository=repository,
        organization_repository=organization_repository,
        project_repository=project_repository,
        semantic_model_service=semantic_model_service,
        snapshot_storage=snapshot_storage,
    )
    return (
        service,
        repository,
        organization_repository,
        project_repository,
        semantic_model_service,
        snapshot_storage,
    )


@pytest.mark.anyio
async def test_create_dashboard_rejects_missing_organization():
    service, _, organization_repository, _, semantic_model_service, _ = _build_service()
    organization_repository.get_by_id.return_value = None
    semantic_model_service.get_model.return_value = SimpleNamespace(project_id=None)

    request = DashboardCreateRequest(
        project_id=None,
        semantic_model_id=uuid.uuid4(),
        name="Revenue",
        global_filters=[],
        widgets=[],
    )

    with pytest.raises(BusinessValidationError, match="Organization not found"):
        await service.create_dashboard(
            organization_id=uuid.uuid4(),
            created_by=uuid.uuid4(),
            request=request,
        )


@pytest.mark.anyio
async def test_create_dashboard_rejects_project_scoped_model_without_project():
    service, _, _, _, semantic_model_service, _ = _build_service()
    scoped_project_id = uuid.uuid4()
    semantic_model_service.get_model.return_value = SimpleNamespace(project_id=scoped_project_id)

    request = DashboardCreateRequest(
        project_id=None,
        semantic_model_id=uuid.uuid4(),
        name="Revenue",
        global_filters=[],
        widgets=[],
    )

    with pytest.raises(
        BusinessValidationError,
        match="Project-scoped semantic models require a project-scoped dashboard",
    ):
        await service.create_dashboard(
            organization_id=uuid.uuid4(),
            created_by=uuid.uuid4(),
            request=request,
        )


@pytest.mark.anyio
async def test_create_dashboard_persists_valid_payload(monkeypatch):
    service, repository, _, project_repository, semantic_model_service, _ = _build_service()
    organization_id = uuid.uuid4()
    created_by = uuid.uuid4()
    project_id = uuid.uuid4()
    semantic_model_id = uuid.uuid4()

    monkeypatch.setattr(dashboard_service_module, "BIDashboard", FakeDashboard)
    project_repository.get_by_id.return_value = SimpleNamespace(id=project_id, organization_id=organization_id)
    semantic_model_service.get_model.return_value = SimpleNamespace(project_id=project_id)

    request = DashboardCreateRequest(
        project_id=project_id,
        semantic_model_id=semantic_model_id,
        name="  Revenue cockpit  ",
        description="  Quarterly KPIs  ",
        global_filters=[{"id": "f-1", "member": "orders.region", "operator": "equals", "values": "US"}],
        widgets=[{"id": "w-1", "title": "Revenue by month"}],
    )

    response = await service.create_dashboard(
        organization_id=organization_id,
        created_by=created_by,
        request=request,
    )

    repository.add.assert_called_once()
    assert response.organization_id == organization_id
    assert response.project_id == project_id
    assert response.semantic_model_id == semantic_model_id
    assert response.created_by == created_by
    assert response.name == "Revenue cockpit"
    assert response.description == "Quarterly KPIs"
    assert response.refresh_mode == "manual"
    assert response.global_filters[0]["member"] == "orders.region"
    assert response.widgets[0]["id"] == "w-1"


@pytest.mark.anyio
async def test_update_dashboard_applies_changes_and_validates_scope(monkeypatch):
    service, repository, _, project_repository, semantic_model_service, _ = _build_service()
    organization_id = uuid.uuid4()
    dashboard_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    current_project_id = uuid.uuid4()
    semantic_model_id = uuid.uuid4()

    monkeypatch.setattr(dashboard_service_module, "BIDashboard", FakeDashboard)
    dashboard = FakeDashboard(
        id=dashboard_id,
        organization_id=organization_id,
        project_id=current_project_id,
        semantic_model_id=semantic_model_id,
        name="Revenue",
        description=None,
        refresh_mode="manual",
        data_snapshot_format="json",
        data_snapshot_reference=None,
        last_refreshed_at=None,
        global_filters=[],
        widgets=[],
        created_by=owner_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    repository.get_for_scope.return_value = dashboard
    project_repository.get_by_id.return_value = SimpleNamespace(
        id=current_project_id,
        organization_id=organization_id,
    )
    semantic_model_service.get_model.return_value = SimpleNamespace(project_id=current_project_id)

    request = DashboardUpdateRequest(
        name="Revenue v2",
        description="Latest finance rollup",
        global_filters=[{"id": "f-1", "member": "orders.region", "operator": "equals", "values": "US"}],
        widgets=[{"id": "w-1", "title": "Revenue by month"}],
    )

    response = await service.update_dashboard(
        dashboard_id=dashboard_id,
        organization_id=organization_id,
        request=request,
    )

    assert response.name == "Revenue v2"
    assert response.description == "Latest finance rollup"
    assert response.global_filters[0]["id"] == "f-1"
    assert response.widgets[0]["title"] == "Revenue by month"


@pytest.mark.anyio
async def test_upsert_dashboard_snapshot_sets_reference_and_refresh_time(monkeypatch):
    service, repository, _, _, _, snapshot_storage = _build_service()
    organization_id = uuid.uuid4()
    dashboard_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(dashboard_service_module, "BIDashboard", FakeDashboard)
    dashboard = FakeDashboard(
        id=dashboard_id,
        organization_id=organization_id,
        project_id=None,
        semantic_model_id=uuid.uuid4(),
        name="Revenue",
        description=None,
        refresh_mode="manual",
        data_snapshot_format="json",
        data_snapshot_reference=None,
        last_refreshed_at=None,
        global_filters=[],
        widgets=[],
        created_by=owner_id,
        created_at=now,
        updated_at=now,
    )
    repository.get_for_scope.return_value = dashboard
    snapshot_storage.write_snapshot.return_value = "org/dashboard.json"

    response = await service.upsert_dashboard_snapshot(
        dashboard_id=dashboard_id,
        organization_id=organization_id,
        request=DashboardSnapshotUpsertRequest(data={"widgets": []}),
    )

    assert response.dashboard_id == dashboard_id
    assert dashboard.data_snapshot_reference == "org/dashboard.json"
    assert dashboard.last_refreshed_at is not None


@pytest.mark.anyio
async def test_get_dashboard_snapshot_returns_none_when_storage_missing(monkeypatch):
    service, repository, _, _, _, snapshot_storage = _build_service()
    organization_id = uuid.uuid4()
    dashboard_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(dashboard_service_module, "BIDashboard", FakeDashboard)
    dashboard = FakeDashboard(
        id=dashboard_id,
        organization_id=organization_id,
        project_id=None,
        semantic_model_id=uuid.uuid4(),
        name="Revenue",
        description=None,
        refresh_mode="manual",
        data_snapshot_format="json",
        data_snapshot_reference="org/dashboard.json",
        last_refreshed_at=now,
        global_filters=[],
        widgets=[],
        created_by=owner_id,
        created_at=now,
        updated_at=now,
    )
    repository.get_for_scope.return_value = dashboard
    snapshot_storage.read_snapshot.return_value = None

    response = await service.get_dashboard_snapshot(
        dashboard_id=dashboard_id,
        organization_id=organization_id,
    )

    assert response is None
