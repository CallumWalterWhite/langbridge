from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from langbridge.apps.api.langbridge_api.auth.dependencies import get_current_user
from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.apps.api.langbridge_api.services.dataset_service import DatasetService
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.datasets import (
    DatasetCatalogResponse,
    DatasetCreateRequest,
    DatasetListResponse,
    DatasetPreviewRequest,
    DatasetPreviewResponse,
    DatasetProfileRequest,
    DatasetProfileResponse,
    DatasetResponse,
    DatasetUpdateRequest,
    DatasetUsageResponse,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
    PermissionDeniedBusinessValidationError,
    ResourceNotFound,
)


router = APIRouter(prefix="/datasets", tags=["datasets"])


def _map_dataset_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionDeniedBusinessValidationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, ResourceNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, BusinessValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Dataset request failed. Error: " + str(exc))


@router.get("", response_model=DatasetListResponse, status_code=status.HTTP_200_OK)
@inject
async def list_datasets(
    workspace_id: UUID = Query(..., description="Workspace (organization) scope id."),
    project_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    tags: list[str] = Query(default_factory=list),
    dataset_types: list[str] = Query(default_factory=list),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> DatasetListResponse:
    try:
        return await service.list_datasets(
            workspace_id=workspace_id,
            project_id=project_id,
            search=search,
            tags=tags,
            dataset_types=dataset_types,
            current_user=current_user,
        )
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_dataset(
    request: DatasetCreateRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> DatasetResponse:
    try:
        return await service.create_dataset(request=request, current_user=current_user)
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc


@router.get("/catalog", response_model=DatasetCatalogResponse, status_code=status.HTTP_200_OK)
@inject
async def get_dataset_catalog(
    workspace_id: UUID = Query(..., description="Workspace (organization) scope id."),
    project_id: UUID | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> DatasetCatalogResponse:
    try:
        return await service.get_catalog(
            workspace_id=workspace_id,
            project_id=project_id,
            current_user=current_user,
        )
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc


@router.get("/{dataset_id}", response_model=DatasetResponse, status_code=status.HTTP_200_OK)
@inject
async def get_dataset(
    dataset_id: UUID,
    workspace_id: UUID = Query(..., description="Workspace (organization) scope id."),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> DatasetResponse:
    try:
        return await service.get_dataset(
            dataset_id=dataset_id,
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc


@router.put("/{dataset_id}", response_model=DatasetResponse, status_code=status.HTTP_200_OK)
@inject
async def update_dataset(
    dataset_id: UUID,
    request: DatasetUpdateRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> DatasetResponse:
    try:
        return await service.update_dataset(
            dataset_id=dataset_id,
            request=request,
            current_user=current_user,
        )
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_dataset(
    dataset_id: UUID,
    workspace_id: UUID = Query(..., description="Workspace (organization) scope id."),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> None:
    try:
        await service.delete_dataset(
            dataset_id=dataset_id,
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc
    return None


@router.post("/{dataset_id}/preview", response_model=DatasetPreviewResponse, status_code=status.HTTP_200_OK)
@inject
async def preview_dataset(
    dataset_id: UUID,
    request: DatasetPreviewRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> DatasetPreviewResponse:
    try:
        return await service.preview_dataset(
            dataset_id=dataset_id,
            request=request,
            current_user=current_user,
        )
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc


@router.post("/{dataset_id}/profile", response_model=DatasetProfileResponse, status_code=status.HTTP_200_OK)
@inject
async def profile_dataset(
    dataset_id: UUID,
    request: DatasetProfileRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> DatasetProfileResponse:
    try:
        return await service.profile_dataset(
            dataset_id=dataset_id,
            request=request,
            current_user=current_user,
        )
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc


@router.get("/{dataset_id}/used-by", response_model=DatasetUsageResponse, status_code=status.HTTP_200_OK)
@inject
async def get_dataset_usage(
    dataset_id: UUID,
    workspace_id: UUID = Query(..., description="Workspace (organization) scope id."),
    current_user: UserResponse = Depends(get_current_user),
    service: DatasetService = Depends(Provide[Container.dataset_service]),
) -> DatasetUsageResponse:
    try:
        return await service.get_usage(
            dataset_id=dataset_id,
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except Exception as exc:
        raise _map_dataset_exception(exc) from exc
