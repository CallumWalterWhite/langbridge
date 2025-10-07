from fastapi import APIRouter, Depends, HTTPException, status
from dependency_injector.wiring import Provide, inject
from ioc import Container
from connectors.config import ConnectorConfigSchema
from errors.application_errors import BusinessValidationError
from schemas.connectors import ConnectorResponse, CreateConnectorRequest, UpdateConnectorRequest
from services.connector_service import ConnectorService

router = APIRouter(prefix="/connectors", tags=["connectors"])

@router.post("/", response_model=ConnectorResponse)
@inject
def create_connector(
    request: CreateConnectorRequest,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
):
    connector = connector_service.create_connector(request)
    return ConnectorResponse.model_validate(connector)

@router.get("/{connector_id}", response_model=ConnectorResponse)
@inject
def get_connector(
    connector_id: str,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
):
    connector = connector_service.get_connector(connector_id)
    return ConnectorResponse.model_validate(connector)

@router.get("/schemas/type", response_model=list[str])
@inject
def list_connector_types(
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
):
    types = connector_service.list_connector_types()
    return types

@router.get("/schema/{connector_type}", response_model=ConnectorConfigSchema)
@inject
def get_connector_schema(
    connector_type: str,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
):
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
    return ConnectorResponse.model_validate(connector)

@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
def delete_connector(
    connector_id: str,
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
):
    connector_service.delete_connector(connector_id)
    return None

@router.get("/", response_model=list[ConnectorResponse])
@inject
def list_connectors(
    connector_service: ConnectorService = Depends(Provide[Container.connector_service]),
):
    connectors = connector_service._connector_repository.get_all()
    return [ConnectorResponse.model_validate(conn) for conn in connectors]
