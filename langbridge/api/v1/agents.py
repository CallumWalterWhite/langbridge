from typing import List, Optional
import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from ioc import Container
from auth.dependencies import get_current_user
from models.auth import UserResponse
from models.llm_connections import (
    LLMConnectionCreate,
    LLMConnectionResponse,
    LLMConnectionTest,
    LLMConnectionUpdate,
)
from services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/llm-connections", response_model=LLMConnectionResponse)
@inject
async def create_llm_connection(
    request: LLMConnectionCreate,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> LLMConnectionResponse:
    return await agent_service.create_llm_connection(
        connection=request,
        current_user=current_user)


@router.get("/llm-connections", response_model=List[LLMConnectionResponse])
@inject
async def list_llm_connections(
    organization_id: Optional[uuid.UUID] = None,
    project_id: Optional[uuid.UUID] = None,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> List[LLMConnectionResponse]:
    return await agent_service.list_llm_connections(
        current_user=current_user,
        organization_id=organization_id,
        project_id=project_id,
    )


@router.get("/llm-connections/{connection_id}", response_model=LLMConnectionResponse)
@inject
async def get_llm_connection(
    connection_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> LLMConnectionResponse:
    connection = await agent_service.get_llm_connection(current_user, connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM Connection not found",
        )
    return connection


@router.put("/llm-connections/{connection_id}", response_model=LLMConnectionResponse)
@inject
async def update_llm_connection(
    connection_id: uuid.UUID,
    request: LLMConnectionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> LLMConnectionResponse:
    connection = await agent_service.update_llm_connection(current_user, connection_id, request)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM Connection not found",
        )
    return connection


@router.post("/llm-connections/test", response_model=dict)
@inject
async def test_llm_connection(
    request: LLMConnectionTest,
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> dict:
    return agent_service.test_llm_connection(request)
