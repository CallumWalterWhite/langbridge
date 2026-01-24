from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from langbridge.apps.api.langbridge_api.auth.dependencies import get_current_user, get_organization
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.semantic_query_builder import (
    QueryBuilderCopilotRequest,
    QueryBuilderCopilotResponse,
)
from langbridge.apps.api.langbridge_api.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/copilot/{organization_id}", tags=["copilot"])


@router.post(
    "/{agent_id}/assist",
    response_model=QueryBuilderCopilotResponse,
    status_code=status.HTTP_200_OK,
)
@inject
async def run_copilot(
    agent_id: UUID,
    organization_id: UUID,
    request: QueryBuilderCopilotRequest,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    orchestrator_service: OrchestratorService = Depends(Provide[Container.orchestrator_service]),
) -> QueryBuilderCopilotResponse:
    try:
        return await orchestrator_service.copilot(
            agent_id=agent_id,
            copilot_request=request,
            current_user=current_user,
        )
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
