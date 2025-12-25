from typing import List, Optional
import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from ioc import Container
from auth.dependencies import get_current_user
from models.auth import UserResponse
from models.agents import AgentDefinitionCreate, AgentDefinitionResponse, AgentDefinitionUpdate
from models.llm_connections import (
    LLMConnectionCreate,
    LLMConnectionResponse,
    LLMConnectionTest,
    LLMConnectionUpdate,
)
from services.agent_service import AgentService
from errors.application_errors import BusinessValidationError

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
    connection = await agent_service.get_llm_connection(
        connection_id=connection_id,
        current_user=current_user,
    )
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

@router.delete("/llm-connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_llm_connection(
    connection_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> None:
    try:
        await agent_service.delete_llm_connection(current_user, connection_id)
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None

# Agent definitions CRUD


@router.post("/definitions", response_model=AgentDefinitionResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_agent_definition(
    request: AgentDefinitionCreate,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> AgentDefinitionResponse:
    # current_user available for future auth; service does not require it yet
    return await agent_service.create_agent_definition(request, current_user)


@router.get("/definitions", response_model=List[AgentDefinitionResponse])
@inject
async def list_agent_definitions(
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> List[AgentDefinitionResponse]:
    return await agent_service.list_agent_definitions(current_user)


@router.get("/definitions/{agent_id}", response_model=AgentDefinitionResponse)
@inject
async def get_agent_definition(
    agent_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> AgentDefinitionResponse:
    agent = await agent_service.get_agent_definition(agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent definition not found")
    return agent


@router.put("/definitions/{agent_id}", response_model=AgentDefinitionResponse)
@inject
async def update_agent_definition(
    agent_id: uuid.UUID,
    request: AgentDefinitionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> AgentDefinitionResponse:
    updated = await agent_service.update_agent_definition(current_user, agent_id, request)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent definition not found")
    return updated


@router.delete("/definitions/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_agent_definition(
    agent_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> None:
    try:
        await agent_service.delete_agent_definition(current_user, agent_id)
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None

@router.get("/definitions/tools/agents", response_model=List[AgentDefinitionResponse])
@inject
async def list_tool_compatible_agents(
    current_user: UserResponse = Depends(get_current_user),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> List[AgentDefinitionResponse]:
    return await agent_service.list_tool_compatible_agents(current_user)