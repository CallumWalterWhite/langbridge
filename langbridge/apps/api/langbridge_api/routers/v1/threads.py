import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from langbridge.apps.api.langbridge_api.auth.dependencies import get_current_user, get_organization
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
    PermissionDeniedBusinessValidationError,
    ResourceNotFound,
)
from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.packages.common.langbridge_common.contracts.threads import (
    ThreadChatRequest,
    ThreadChatResponse,
    ThreadCreateRequest,
    ThreadHistoryResponse,
    ThreadListResponse,
    ThreadResponse,
    ThreadUpdateRequest,
)
from langbridge.apps.api.langbridge_api.services.orchestrator_service import OrchestratorService
from langbridge.apps.api.langbridge_api.services.thread_service import ThreadService

router = APIRouter(prefix="/thread/{organization_id}", tags=["threads"])


@router.get("/", response_model=ThreadListResponse)
@inject
async def list_threads(
    organization_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    thread_service: ThreadService = Depends(Provide[Container.thread_service]),
) -> ThreadListResponse:
    threads = await thread_service.list_threads_for_user(current_user)
    return ThreadListResponse(threads=threads)


@router.post("/", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_thread(
    request: ThreadCreateRequest,
    organization_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    thread_service: ThreadService = Depends(Provide[Container.thread_service]),
) -> ThreadResponse:
    try:
        thread = await thread_service.create_thread(request, current_user)
    except PermissionDeniedBusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return thread


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_thread(
    thread_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    thread_service: ThreadService = Depends(Provide[Container.thread_service]),
) -> None:
    try:
        await thread_service.delete_thread(thread_id, current_user)
    except ResourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedBusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return None


# @router.get("/{thread_id}", response_model=ThreadResponse)
# @inject
# async def get_thread(
#     thread_id: uuid.UUID,
#     organization_id: uuid.UUID,
#     current_user: UserResponse = Depends(get_current_user),
#     _org = Depends(get_organization),
#     thread_service: ThreadService = Depends(Provide[Container.thread_service]),
# ) -> ThreadResponse:
#     try:
#         thread = await thread_service.get_thread_for_user(thread_id, current_user)
#     except ResourceNotFound as exc:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
#     except PermissionDeniedBusinessValidationError as exc:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
#     return ThreadResponse.model_validate(thread)


@router.put("/{thread_id}", response_model=ThreadResponse)
@inject
async def update_thread(
    thread_id: uuid.UUID,
    request: ThreadUpdateRequest,
    organization_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    thread_service: ThreadService = Depends(Provide[Container.thread_service]),
) -> ThreadResponse:
    try:
        thread = await thread_service.update_thread(thread_id, current_user, request=request)
    except ResourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedBusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return thread


@router.post("/{thread_id}/chat", response_model=ThreadChatResponse)
@inject
async def chat_thread(
    thread_id: uuid.UUID,
    request: ThreadChatRequest,
    organization_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    thread_service: ThreadService = Depends(Provide[Container.thread_service]),
    orchestrator_service: OrchestratorService = Depends(Provide[Container.orchestrator_service]),
) -> ThreadChatResponse:
    """Handle a chat request within a specific thread."""
    try:
        await thread_service.get_thread_for_user(thread_id, current_user)
    except ResourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedBusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    try:
        response = await orchestrator_service.chat(
            msg=request.message,
            agent_id=request.agent_id,
            thread_id=thread_id,
            current_user=current_user,
        )
        await thread_service.record_chat_turn(
            thread_id,
            current_user,
            prompt=request.message,
            response=response,
            agent_snapshot={"agent_id": str(request.agent_id)},
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ThreadChatResponse(
        result=response.get("result"),
        visualization=response.get("visualization"),
        summary=response.get("summary"),
    )


@router.get("/{thread_id}/messages", response_model=ThreadHistoryResponse)
@inject
async def list_thread_messages(
    thread_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    thread_service: ThreadService = Depends(Provide[Container.thread_service]),
) -> ThreadHistoryResponse:
    try:
        messages = await thread_service.list_messages_for_thread(thread_id, current_user)
    except ResourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedBusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return ThreadHistoryResponse(messages=messages)


@router.get("/test", response_model=dict[str, str])
@inject
async def create_thread(
    organization_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    orchestrator_service: OrchestratorService = Depends(Provide[Container.orchestrator_service]),
) -> dict[str, str]:
    await orchestrator_service.send_agent_job_request()
    return {"message": "Test endpoint is working!"}