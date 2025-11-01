from typing import Optional
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from errors.application_errors import BusinessValidationError
from ioc import Container
from schemas.semantic_models import (
    SemanticModelCreateRequest,
    SemanticModelRecordResponse,
)
from services.semantic_model_service import SemanticModelService

router = APIRouter(prefix="/semantic-model", tags=["semantic-model"])


@router.get("/generate/yaml")
@inject
async def preview_semantic_model_yaml(
    connector_id: UUID,
    service: SemanticModelService = Depends(Provide[Container.semantic_model_service]),
) -> PlainTextResponse:
    try:
        yaml_text = await service.generate_model_yaml(connector_id)
        return PlainTextResponse(yaml_text, media_type="text/yaml")
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/",
    response_model=SemanticModelRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_semantic_model(
    request: SemanticModelCreateRequest,
    service: SemanticModelService = Depends(Provide[Container.semantic_model_service]),
) -> SemanticModelRecordResponse:
    try:
        entry = await service.create_model(request)
        return SemanticModelRecordResponse.model_validate(entry)
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/", response_model=list[SemanticModelRecordResponse])
@inject
async def list_semantic_models(
    organization_id: UUID,
    project_id: Optional[UUID] = None,
    service: SemanticModelService = Depends(Provide[Container.semantic_model_service]),
) -> list[SemanticModelRecordResponse]:
    models = await service.list_models(
        organization_id=organization_id,
        project_id=project_id,
    )
    return [SemanticModelRecordResponse.model_validate(model) for model in models]


@router.get("/{model_id}", response_model=SemanticModelRecordResponse)
@inject
async def get_semantic_model(
    model_id: UUID,
    organization_id: UUID,
    service: SemanticModelService = Depends(Provide[Container.semantic_model_service]),
) -> SemanticModelRecordResponse:
    try:
        model = await service.get_model(model_id=model_id, organization_id=organization_id)
        return SemanticModelRecordResponse.model_validate(model)
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/{model_id}/yaml")
@inject
async def get_semantic_model_yaml(
    model_id: UUID,
    organization_id: UUID,
    service: SemanticModelService = Depends(Provide[Container.semantic_model_service]),
) -> PlainTextResponse:
    try:
        model = await service.get_model(model_id=model_id, organization_id=organization_id)
        return PlainTextResponse(model.content_yaml, media_type="text/yaml")
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_semantic_model(
    model_id: UUID,
    organization_id: UUID,
    service: SemanticModelService = Depends(Provide[Container.semantic_model_service]),
) -> None:
    try:
        await service.delete_model(model_id=model_id, organization_id=organization_id)
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return None
