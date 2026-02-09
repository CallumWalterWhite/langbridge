from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from langbridge.apps.api.langbridge_api.auth.dependencies import get_current_user, get_organization
from langbridge.apps.api.langbridge_api.services.jobs.semantic_query_job_request_service import (
    SemanticQueryJobRequestService,
)
from langbridge.packages.common.langbridge_common.contracts.jobs.semantic_query_job import (
    CreateSemanticQueryJobRequest,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.semantic import (
    SemanticQueryJobResponse,
    SemanticQueryMetaResponse,
    SemanticQueryRequest,
    SemanticQueryResponse,
)
from langbridge.apps.api.langbridge_api.services.semantic import SemanticQueryService

router = APIRouter(prefix="/semantic-query/{organization_id}", tags=["semantic-query"])

@router.post(
    "/{semantic_model_id}/q",
    response_model=SemanticQueryResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def semantic_query(
    request: SemanticQueryRequest,
    semantic_model_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    service: SemanticQueryService = Depends(Provide[Container.semantic_query_service]),
) -> SemanticQueryResponse:
    try:
        return await service.query_request(request)
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post(
    "/{semantic_model_id}/q/jobs",
    response_model=SemanticQueryJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def semantic_query_enqueue(
    request: SemanticQueryRequest,
    semantic_model_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    service: SemanticQueryJobRequestService = Depends(
        Provide[Container.semantic_query_job_request_service]
    ),
) -> SemanticQueryJobResponse:
    if request.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization_id in path and body must match.",
        )
    if request.semantic_model_id != semantic_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="semantic_model_id in path and body must match.",
        )

    if request.project_id and current_user.available_projects is not None:
        allowed = {str(project_id) for project_id in current_user.available_projects}
        if str(request.project_id) not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        job = await service.create_semantic_query_job_request(
            request=CreateSemanticQueryJobRequest(
                organisation_id=organization_id,
                project_id=request.project_id,
                user_id=current_user.id,
                semantic_model_id=semantic_model_id,
                query=request.query,
            ),
        )
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SemanticQueryJobResponse(
        job_id=job.id,
        job_status=(job.status.value if job.status is not None else "queued"),
    )

@router.get(
    "/{semantic_model_id}/meta",
    response_model=SemanticQueryMetaResponse,
    status_code=status.HTTP_200_OK,
)
@inject
async def semantic_query_meta(
    semantic_model_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    service: SemanticQueryService = Depends(Provide[Container.semantic_query_service]),
) -> SemanticQueryMetaResponse:
    try:
        return await service.get_meta(
            semantic_model_id=semantic_model_id,
            organization_id=organization_id,
        )
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
