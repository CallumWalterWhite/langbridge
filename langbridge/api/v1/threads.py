import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from auth.dependencies import get_current_user
from models.auth import UserResponse
from errors.application_errors import (
    BusinessValidationError,
    PermissionDeniedBusinessValidationError,
    ResourceNotFound,
)
from ioc import Container
from models.threads import (
    ThreadChatRequest,
    ThreadChatResponse,
    ThreadCreateRequest,
    ThreadListResponse,
    ThreadResponse,
)
from services.orchestrator_service import OrchestratorService
from services.thread_service import ThreadService

router = APIRouter(prefix="/thread", tags=["threads"])


@router.get("/", response_model=ThreadListResponse)
@inject
async def list_threads(
    current_user: UserResponse = Depends(get_current_user),
    thread_service: ThreadService = Depends(Provide[Container.thread_service]),
) -> ThreadListResponse:
    threads = await thread_service.list_threads_for_user(current_user)
    return ThreadListResponse(threads=threads)


@router.post("/", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_thread(
    request: ThreadCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
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
    current_user: UserResponse = Depends(get_current_user),
    thread_service: ThreadService = Depends(Provide[Container.thread_service]),
) -> None:
    try:
        await thread_service.delete_thread(thread_id, current_user)
    except ResourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedBusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return None


@router.post("/{thread_id}/chat", response_model=ThreadChatResponse)
@inject
async def chat_thread(
    thread_id: uuid.UUID,
    request: ThreadChatRequest,
    current_user: UserResponse = Depends(get_current_user),
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
            current_user=current_user,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ThreadChatResponse(
        result=response.get("result"),
        visualization=response.get("visualization"),
        summary=response.get("summary"),
    )
