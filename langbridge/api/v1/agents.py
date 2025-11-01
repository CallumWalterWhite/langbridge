from typing import List

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from ioc import Container
from schemas.llm_connections import (
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
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> LLMConnectionResponse:
    connection = await agent_service.create_llm_connection(request)
    return LLMConnectionResponse.model_validate(connection)


@router.get("/llm-connections", response_model=List[LLMConnectionResponse])
@inject
async def list_llm_connections(
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> List[LLMConnectionResponse]:
    connections = await agent_service.list_llm_connections()
    return [LLMConnectionResponse.model_validate(conn) for conn in connections]


@router.get("/llm-connections/{connection_id}", response_model=LLMConnectionResponse)
@inject
async def get_llm_connection(
    connection_id: int,
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> LLMConnectionResponse:
    connection = await agent_service.get_llm_connection(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM Connection not found",
        )
    return LLMConnectionResponse.model_validate(connection)


@router.put("/llm-connections/{connection_id}", response_model=LLMConnectionResponse)
@inject
async def update_llm_connection(
    connection_id: int,
    request: LLMConnectionUpdate,
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> LLMConnectionResponse:
    connection = await agent_service.update_llm_connection(connection_id, request)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM Connection not found",
        )
    return LLMConnectionResponse.model_validate(connection)


@router.post("/llm-connections/test", response_model=dict)
@inject
async def test_llm_connection(
    request: LLMConnectionTest,
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
) -> dict:
    return agent_service.test_llm_connection(request)
