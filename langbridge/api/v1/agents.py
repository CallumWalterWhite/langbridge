from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .datasources import _DATA_SOURCES, _to_camel


AgentKind = Literal['sql_analyst', 'docs_qa', 'hybrid']


class Agent(BaseModel):
    id: str
    name: str
    kind: AgentKind
    source_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, frozen=True)


class AgentCreate(BaseModel):
    name: str
    kind: AgentKind
    source_ids: List[str] = Field(default_factory=list)


class AgentCreateResponse(BaseModel):
    id: str


router = APIRouter(prefix='/agents', tags=['agents'])


_AGENTS: Dict[str, Agent] = {}


@router.get('', response_model=List[Agent])
async def list_agents() -> List[Agent]:
    return list(_AGENTS.values())


@router.post('', response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: AgentCreate) -> AgentCreateResponse:
    if not payload.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Name is required')

    missing_sources = [source_id for source_id in payload.source_ids if source_id not in _DATA_SOURCES]
    if missing_sources:
        detail = f"Unknown data source ids: {', '.join(missing_sources)}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    identifier = str(uuid4())
    agent = Agent(
        id=identifier,
        name=payload.name.strip(),
        kind=payload.kind,
        source_ids=payload.source_ids,
    )
    _AGENTS[identifier] = agent
    return AgentCreateResponse(id=identifier)

