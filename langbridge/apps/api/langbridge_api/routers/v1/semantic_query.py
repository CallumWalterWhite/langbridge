from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from langbridge.apps.api.langbridge_api.auth.dependencies import get_current_user, get_organization
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.semantic import (
    SemanticQueryRequest,
    SemanticQueryResponse,
    SemanticQueryMetaResponse
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
