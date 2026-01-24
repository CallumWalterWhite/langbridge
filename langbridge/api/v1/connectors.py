from typing import Optional
from uuid import UUID
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from auth.dependencies import get_current_user, get_organization, get_project
from connectors.config import ConnectorConfigSchema
from errors.application_errors import BusinessValidationError
from ioc import Container
from models.auth import UserResponse
from models.connectors import (
    ConnectorResponse,
    ConnectorSourceSchemaColumnResponse,
    ConnectorSourceSchemaResponse,
    ConnectorSourceSchemaTableResponse,
    ConnectorSourceSchemasResponse,
    CreateConnectorRequest,
    UpdateConnectorRequest,
)
from services.connector_schema_service import ConnectorSchemaService
from services.connector_service import ConnectorService

router = APIRouter(prefix="/connectors/{organization_id}", tags=["connectors"])


@router.post("/", response_model=ConnectorResponse)
@inject
async def create_connector(
    request: CreateConnectorRequest,
    organization_id: UUID,
    project_id: Optional[UUID] = None,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    _proj = Depends(get_project),
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> ConnectorResponse:
    return await connector_service.create_connector(request)


@router.get("/{connector_id}", response_model=ConnectorResponse)
@inject
async def get_connector(
    connector_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> ConnectorResponse:
    return await connector_service.get_connector(connector_id)


@router.get("/{connector_id}/source/schemas", response_model=ConnectorSourceSchemasResponse)
@inject
async def get_connector_schemas(
    connector_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    connector_schema_service: ConnectorSchemaService = Depends(
        Provide[Container.connector_schema_service]
    ),
) -> ConnectorSourceSchemasResponse:
    schemas = await connector_schema_service.get_schemas(connector_id)
    return ConnectorSourceSchemasResponse(schemas=schemas)


@router.get(
    "/{connector_id}/source/schema/{schema}",
    response_model=ConnectorSourceSchemaResponse,
)
@inject
async def get_connector_tables(
    connector_id: UUID,
    schema: str,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    connector_schema_service: ConnectorSchemaService = Depends(
        Provide[Container.connector_schema_service]
    ),
) -> ConnectorSourceSchemaResponse:
    tables = await connector_schema_service.get_tables(connector_id, schema)
    return ConnectorSourceSchemaResponse(schema=schema, tables=tables)


@router.get(
    "/{connector_id}/source/schema/{schema}/table/{table}/columns",
    response_model=ConnectorSourceSchemaTableResponse,
)
@inject
async def get_connector_table(
    connector_id: UUID,
    schema: str,
    table: str,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    connector_schema_service: ConnectorSchemaService = Depends(
        Provide[Container.connector_schema_service]
    ),
) -> ConnectorSourceSchemaTableResponse:
    columns = await connector_schema_service.get_columns(connector_id, schema, table)
    return ConnectorSourceSchemaTableResponse(
        name=table,
        columns={
            column.name: ConnectorSourceSchemaColumnResponse(
                name=column.name,
                type=column.data_type,
                nullable=getattr(column, "nullable", None),
                primary_key=getattr(column, "primary_key", False),
            )
            for column in columns
        },
    )


@router.get("/schemas/type", response_model=list[str])
@inject
async def list_connector_types(
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> list[str]:
    return connector_service.list_connector_types()


@router.get("/schema/{connector_type}", response_model=ConnectorConfigSchema)
@inject
async def get_connector_schema(
    connector_type: str,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> ConnectorConfigSchema:
    try:
        return connector_service.get_connector_config_schema(connector_type)
    except BusinessValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.put("/{connector_id}", response_model=ConnectorResponse)
@inject
async def update_connector(
    connector_id: UUID,
    request: UpdateConnectorRequest,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> ConnectorResponse:
    return await connector_service.update_connector(connector_id, request)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_connector(
    connector_id: UUID,
    organization_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> None:
    await connector_service.delete_connector(connector_id)
    return None


@router.get("/", response_model=list[ConnectorResponse])
@inject
async def list_connectors(
    organization_id: UUID,
    project_id: Optional[UUID] = None,
    current_user: UserResponse = Depends(get_current_user),
    _org = Depends(get_organization),
    _proj = Depends(get_project),
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> list[ConnectorResponse]:
    if project_id:
        return await connector_service.list_project_connectors(project_id)
    return await connector_service.list_organization_connectors(organization_id)
