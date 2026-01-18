from typing import Optional
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from auth.dependencies import has_organization_access, has_project_access
from errors.application_errors import BusinessValidationError
from ioc import Container
from models.auth import UserResponse
from models.semantic import (
    SemanticQueryRequest,
    SemanticQueryResponse,
    SemanticQueryMetaResponse
)
from services.semantic import SemanticQueryService

router = APIRouter(prefix="/semantic-query", tags=["semantic-query"])

@router.post(
    "/{semantic_model_id}/q",
    response_model=SemanticQueryResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def semantic_query(
    request: SemanticQueryRequest,
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
