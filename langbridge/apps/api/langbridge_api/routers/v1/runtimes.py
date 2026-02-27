from datetime import datetime
import uuid
from typing import List

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from langbridge.apps.api.langbridge_api.auth.dependencies import get_current_user, get_organization
from langbridge.apps.api.langbridge_api.auth.runtime_dependencies import (
    RuntimePrincipal,
    get_runtime_principal,
)
from langbridge.apps.api.langbridge_api.ioc.container import Container
from langbridge.apps.api.langbridge_api.services.runtime_registry_service import RuntimeRegistryService
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.runtime import (
    RuntimeCapabilitiesUpdateRequest,
    RuntimeCapabilitiesUpdateResponse,
    RuntimeHeartbeatRequest,
    RuntimeHeartbeatResponse,
    RuntimeInstanceResponse,
    RuntimeRegistrationRequest,
    RuntimeRegistrationResponse,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.common.langbridge_common.contracts.base import _Base


class RuntimeRegistrationTokenResponse(_Base):
    registration_token: str
    expires_at: datetime


router = APIRouter(prefix="/runtimes", tags=["runtimes"])


@router.post("/register", response_model=RuntimeRegistrationResponse)
@inject
async def register_runtime(
    request: RuntimeRegistrationRequest,
    runtime_registry_service: RuntimeRegistryService = Depends(
        Provide[Container.runtime_registry_service]
    ),
) -> RuntimeRegistrationResponse:
    try:
        return await runtime_registry_service.register_runtime(request)
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/heartbeat", response_model=RuntimeHeartbeatResponse)
@inject
async def runtime_heartbeat(
    request: RuntimeHeartbeatRequest,
    principal: RuntimePrincipal = Depends(get_runtime_principal),
    runtime_registry_service: RuntimeRegistryService = Depends(
        Provide[Container.runtime_registry_service]
    ),
) -> RuntimeHeartbeatResponse:
    try:
        return await runtime_registry_service.heartbeat(
            tenant_id=principal.tenant_id,
            ep_id=principal.ep_id,
            request=request,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/capabilities", response_model=RuntimeCapabilitiesUpdateResponse)
@inject
async def update_runtime_capabilities(
    request: RuntimeCapabilitiesUpdateRequest,
    principal: RuntimePrincipal = Depends(get_runtime_principal),
    runtime_registry_service: RuntimeRegistryService = Depends(
        Provide[Container.runtime_registry_service]
    ),
) -> RuntimeCapabilitiesUpdateResponse:
    try:
        return await runtime_registry_service.update_capabilities(
            tenant_id=principal.tenant_id,
            ep_id=principal.ep_id,
            request=request,
        )
    except BusinessValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/{organization_id}/tokens",
    response_model=RuntimeRegistrationTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_runtime_registration_token(
    organization_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    runtime_registry_service: RuntimeRegistryService = Depends(
        Provide[Container.runtime_registry_service]
    ),
) -> RuntimeRegistrationTokenResponse:
    token, expires_at = await runtime_registry_service.create_registration_token(
        tenant_id=organization_id,
        created_by_user_id=current_user.id,
    )
    return RuntimeRegistrationTokenResponse(registration_token=token, expires_at=expires_at)


@router.get(
    "/{organization_id}/instances",
    response_model=List[RuntimeInstanceResponse],
)
@inject
async def list_runtime_instances(
    organization_id: uuid.UUID,
    _current_user: UserResponse = Depends(get_current_user),
    _org=Depends(get_organization),
    runtime_registry_service: RuntimeRegistryService = Depends(
        Provide[Container.runtime_registry_service]
    ),
) -> List[RuntimeInstanceResponse]:
    return await runtime_registry_service.list_runtimes_for_tenant(tenant_id=organization_id)
