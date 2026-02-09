from typing import Optional
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from langbridge.apps.api.langbridge_api.auth.dependencies import (
    get_current_user,
    get_organization,
    get_project,
)
from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.apps.api.langbridge_api.services.dashboard_service import DashboardService
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.dashboards import (
    DashboardCreateRequest,
    DashboardResponse,
    DashboardSnapshotResponse,
    DashboardSnapshotUpsertRequest,
    DashboardUpdateRequest,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
)

router = APIRouter(prefix="/bi-dashboard/{organization_id}", tags=["bi-dashboard"])


def _require_project_access_if_needed(
    *,
    project_id: UUID | None,
    current_user: UserResponse,
) -> None:
    if project_id is None:
        return
    if current_user.available_projects is None:
        return
    available = {str(project) for project in current_user.available_projects}
    if str(project_id) not in available:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/", response_model=list[DashboardResponse], status_code=status.HTTP_200_OK)
@inject
async def list_dashboards(
    organization_id: UUID,
    project_id: Optional[UUID] = None,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    _proj=Depends(get_project),
    service: DashboardService = Depends(Provide[Container.dashboard_service]),
) -> list[DashboardResponse]:
    try:
        return await service.list_dashboards(
            organization_id=organization_id,
            project_id=project_id,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_dashboard(
    request: DashboardCreateRequest,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    service: DashboardService = Depends(Provide[Container.dashboard_service]),
) -> DashboardResponse:
    _require_project_access_if_needed(project_id=request.project_id, current_user=current_user)
    try:
        return await service.create_dashboard(
            organization_id=organization_id,
            created_by=current_user.id,
            request=request,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{dashboard_id}",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
)
@inject
async def get_dashboard(
    dashboard_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    service: DashboardService = Depends(Provide[Container.dashboard_service]),
) -> DashboardResponse:
    try:
        return await service.get_dashboard(
            dashboard_id=dashboard_id,
            organization_id=organization_id,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/{dashboard_id}",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
)
@inject
async def update_dashboard(
    dashboard_id: UUID,
    request: DashboardUpdateRequest,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    service: DashboardService = Depends(Provide[Container.dashboard_service]),
) -> DashboardResponse:
    if "project_id" in request.model_fields_set:
        _require_project_access_if_needed(project_id=request.project_id, current_user=current_user)
    try:
        return await service.update_dashboard(
            dashboard_id=dashboard_id,
            organization_id=organization_id,
            request=request,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/{dashboard_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def delete_dashboard(
    dashboard_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    service: DashboardService = Depends(Provide[Container.dashboard_service]),
) -> None:
    try:
        await service.delete_dashboard(
            dashboard_id=dashboard_id,
            organization_id=organization_id,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.get(
    "/{dashboard_id}/snapshot",
    response_model=DashboardSnapshotResponse | None,
    status_code=status.HTTP_200_OK,
)
@inject
async def get_dashboard_snapshot(
    dashboard_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    service: DashboardService = Depends(Provide[Container.dashboard_service]),
) -> DashboardSnapshotResponse | None:
    try:
        return await service.get_dashboard_snapshot(
            dashboard_id=dashboard_id,
            organization_id=organization_id,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/{dashboard_id}/snapshot",
    response_model=DashboardSnapshotResponse,
    status_code=status.HTTP_200_OK,
)
@inject
async def upsert_dashboard_snapshot(
    dashboard_id: UUID,
    request: DashboardSnapshotUpsertRequest,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    service: DashboardService = Depends(Provide[Container.dashboard_service]),
) -> DashboardSnapshotResponse:
    try:
        return await service.upsert_dashboard_snapshot(
            dashboard_id=dashboard_id,
            organization_id=organization_id,
            request=request,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
