import uuid
from dataclasses import dataclass

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, Request, status

from langbridge.apps.api.langbridge_api.ioc.container import Container
from langbridge.apps.api.langbridge_api.services.runtime_auth_service import (
    RuntimeAuthError,
    RuntimeAuthService,
)


@dataclass(frozen=True)
class RuntimePrincipal:
    tenant_id: uuid.UUID
    ep_id: uuid.UUID


@inject
def get_runtime_principal(
    request: Request,
    runtime_auth_service: RuntimeAuthService = Depends(Provide[Container.runtime_auth_service]),
) -> RuntimePrincipal:
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing runtime bearer token.",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = runtime_auth_service.verify_runtime_access_token(token)
        tenant_id, ep_id = runtime_auth_service.parse_runtime_claims(claims)
    except RuntimeAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return RuntimePrincipal(tenant_id=tenant_id, ep_id=ep_id)
