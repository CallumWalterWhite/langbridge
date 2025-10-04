from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from utils.schema import _to_camel


DataSourceType = Literal['snowflake', 'postgres', 'mysql', 'api']
DataSourceStatus = Literal['connected', 'error', 'pending']


class DataSource(BaseModel):
    id: str
    name: str
    type: DataSourceType
    status: DataSourceStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, frozen=True)


class DataSourceCreate(BaseModel):
    name: str
    type: DataSourceType
    config: dict | None = None


class DataSourceCreateResponse(BaseModel):
    id: str


router = APIRouter(prefix='/datasources', tags=['datasources'])


_DATA_SOURCES: Dict[str, DataSource] = {}


@router.get('', response_model=List[DataSource])
async def list_data_sources() -> List[DataSource]:
    return list(_DATA_SOURCES.values())


@router.post('', response_model=DataSourceCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_data_source(payload: DataSourceCreate) -> DataSourceCreateResponse:
    if not payload.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Name is required')

    identifier = str(uuid4())
    data_source = DataSource(
        id=identifier,
        name=payload.name.strip(),
        type=payload.type,
        status='connected',
    )
    _DATA_SOURCES[identifier] = data_source
    return DataSourceCreateResponse(id=identifier)
