from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from langbridge.apps.api.langbridge_api.auth.dependencies import get_current_user, get_organization
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.apps.api.langbridge_api.services.jobs.copilot_dashboard_job_request_service import (
    CopilotDashboardJobRequestService,
)
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.jobs.copilot_dashboard_job import (
    CopilotDashboardAssistRequest,
    CopilotDashboardJobResponse,
    CreateCopilotDashboardJobRequest,
)
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


@router.post(
    "/{agent_id}/assist/jobs",
    response_model=CopilotDashboardJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def enqueue_copilot_job(
    agent_id: UUID,
    organization_id: UUID,
    request: CopilotDashboardAssistRequest,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    service: CopilotDashboardJobRequestService = Depends(
        Provide[Container.copilot_dashboard_job_request_service]
    ),
) -> CopilotDashboardJobResponse:
    if request.project_id and current_user.available_projects is not None:
        allowed = {str(project_id) for project_id in current_user.available_projects}
        if str(request.project_id) not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        job = await service.create_copilot_dashboard_job_request(
            request=CreateCopilotDashboardJobRequest(
                organisation_id=organization_id,
                project_id=request.project_id,
                user_id=current_user.id,
                agent_definition_id=agent_id,
                semantic_model_id=request.semantic_model_id,
                instructions=request.instructions,
                dashboard_name=request.dashboard_name,
                current_dashboard=request.current_dashboard,
                generate_previews=request.generate_previews,
                max_widgets=request.max_widgets,
            )
        )
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return CopilotDashboardJobResponse(
        job_id=job.id,
        job_status=(job.status.value if job.status is not None else "queued"),
    )
