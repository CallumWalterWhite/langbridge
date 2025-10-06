from fastapi import APIRouter, Depends, HTTPException, status
from dependency_injector.wiring import Provide, inject
from ioc import Container
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
