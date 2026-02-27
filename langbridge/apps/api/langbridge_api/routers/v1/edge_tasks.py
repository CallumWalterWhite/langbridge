from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from langbridge.apps.api.langbridge_api.auth.runtime_dependencies import (
    RuntimePrincipal,
    get_runtime_principal,
)
from langbridge.apps.api.langbridge_api.ioc.container import Container
from langbridge.apps.api.langbridge_api.services.edge_task_gateway_service import (
    EdgeTaskGatewayService,
)
from langbridge.packages.common.langbridge_common.contracts.runtime import (
    EdgeTaskAckRequest,
    EdgeTaskAckResponse,
    EdgeTaskFailRequest,
    EdgeTaskFailResponse,
    EdgeTaskPullRequest,
    EdgeTaskPullResponse,
    EdgeTaskResultRequest,
    EdgeTaskResultResponse,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
)


router = APIRouter(prefix="/edge/tasks", tags=["edge"])


@router.post("/pull", response_model=EdgeTaskPullResponse)
@inject
async def pull_tasks(
    request: EdgeTaskPullRequest,
    principal: RuntimePrincipal = Depends(get_runtime_principal),
    edge_task_gateway_service: EdgeTaskGatewayService = Depends(
        Provide[Container.edge_task_gateway_service]
    ),
) -> EdgeTaskPullResponse:
    try:
        tasks = await edge_task_gateway_service.pull_tasks(
            tenant_id=principal.tenant_id,
            runtime_id=principal.ep_id,
            request=request,
        )
        return EdgeTaskPullResponse(tasks=tasks)
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/ack", response_model=EdgeTaskAckResponse)
@inject
async def ack_task(
    request: EdgeTaskAckRequest,
    principal: RuntimePrincipal = Depends(get_runtime_principal),
    edge_task_gateway_service: EdgeTaskGatewayService = Depends(
        Provide[Container.edge_task_gateway_service]
    ),
) -> EdgeTaskAckResponse:
    try:
        return await edge_task_gateway_service.ack_task(
            tenant_id=principal.tenant_id,
            runtime_id=principal.ep_id,
            request=request,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/result", response_model=EdgeTaskResultResponse)
@inject
async def post_task_result(
    request: EdgeTaskResultRequest,
    principal: RuntimePrincipal = Depends(get_runtime_principal),
    edge_task_gateway_service: EdgeTaskGatewayService = Depends(
        Provide[Container.edge_task_gateway_service]
    ),
) -> EdgeTaskResultResponse:
    try:
        return await edge_task_gateway_service.ingest_result(
            tenant_id=principal.tenant_id,
            runtime_id=principal.ep_id,
            request=request,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/fail", response_model=EdgeTaskFailResponse)
@inject
async def fail_task(
    request: EdgeTaskFailRequest,
    principal: RuntimePrincipal = Depends(get_runtime_principal),
    edge_task_gateway_service: EdgeTaskGatewayService = Depends(
        Provide[Container.edge_task_gateway_service]
    ),
) -> EdgeTaskFailResponse:
    try:
        return await edge_task_gateway_service.fail_task(
            tenant_id=principal.tenant_id,
            runtime_id=principal.ep_id,
            request=request,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
