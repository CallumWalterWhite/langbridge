from fastapi import APIRouter, Depends, HTTPException, status
from dependency_injector.wiring import Provide, inject
from ioc import Container
from connectors.config import ConnectorConfigSchema
from errors.application_errors import BusinessValidationError
from db.connector import Connector
from schemas.connectors import (
    ConnectorResponse, 
    CreateConnectorRequest, 
    UpdateConnectorRequest,
    ConnectorSourceSchemasResponse,
    ConnectorSourceSchemaResponse,
    ConnectorSourceSchemaColumnResponse,
    ConnectorSourceSchemaTableResponse
)
from services.connector_service import ConnectorService
from services.connector_schema_service import ConnectorSchemaService

router = APIRouter(prefix="/connectors", tags=["connectors"])

@router.post("/", response_model=ConnectorResponse)
@inject
def create_connector(
    request: CreateConnectorRequest,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> ConnectorResponse:
    connector: Connector = connector_service.create_connector(request)
    return ConnectorResponse.from_connector(connector)

@router.get("/{connector_id}", response_model=ConnectorResponse)
@inject
def get_connector(
    connector_id: str,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> ConnectorResponse:
    connector = connector_service.get_connector(connector_id)
    return ConnectorResponse.from_connector(connector)

@router.get("/{connector_id}/source/schemas", response_model=ConnectorResponse)
@inject
def get_connector_schemas(
    connector_id: str,
    connector_schema_service: ConnectorSchemaService = Depends(Provide[Container.connector_schema_service]),
) -> ConnectorSourceSchemasResponse:
    schemas = connector_schema_service.get_schemas(connector_id)
    return ConnectorSourceSchemasResponse(schemas=schemas)

@router.get("/{connector_id}/source/schema/{schema}", response_model=ConnectorSourceSchemaResponse)
@inject
def get_connector_tables(
    connector_id: str,
    schema: str,
    connector_schema_service: ConnectorSchemaService = Depends(Provide[Container.connector_schema_service]),
) -> ConnectorSourceSchemaResponse:
    tables = connector_schema_service.get_tables(connector_id, schema)
    return ConnectorSourceSchemaResponse(schema=schema, tables=tables)

@router.get("/{connector_id}/source/schema/{schema}/table/{table}/columns", response_model=ConnectorSourceSchemaColumnResponse)
@inject
def get_connector_table(
    connector_id: str,
    schema: str,
    table: str,
    connector_schema_service: ConnectorSchemaService = Depends(Provide[Container.connector_schema_service]),
) -> ConnectorSourceSchemaColumnResponse:
    columns = connector_schema_service.get_columns(connector_id, schema, table)
    return ConnectorSourceSchemaTableResponse(columns=[
        ConnectorSourceSchemaColumnResponse(name=col.name, type=col.data_type) for col in columns
    ]) # type: ignore

@router.get("/schemas/type", response_model=list[str])
@inject
def list_connector_types(
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> list[str]:
    types = connector_service.list_connector_types()
    return types

@router.get("/schema/{connector_type}", response_model=ConnectorConfigSchema)
@inject
def get_connector_schema(
    connector_type: str,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> ConnectorConfigSchema:
    try:
        schema = connector_service.get_connector_config_schema(connector_type)
        return schema
    except BusinessValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/{connector_id}", response_model=ConnectorResponse)
@inject
def update_connector(
    connector_id: str,
    request: UpdateConnectorRequest,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
):
    connector = connector_service.update_connector(connector_id, request)
    return ConnectorResponse.from_connector(connector)

@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
def delete_connector(
    connector_id: str,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> None:
    connector_service.delete_connector(connector_id)
    return None

@router.get("/", response_model=list[ConnectorResponse])
@inject
def list_connectors(
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
) -> list[ConnectorResponse]:
    connectors = connector_service._connector_repository.get_all()
    return [ConnectorResponse.from_connector(conn) for conn in connectors]
