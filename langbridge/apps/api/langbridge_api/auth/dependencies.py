from typing import Optional
import uuid
from fastapi import Depends, HTTPException, Query, Request, Path, status
from dependency_injector.wiring import Provide, inject

from langbridge.apps.api.langbridge_api.ioc.container import Container
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.organizations import OrganizationResponse, ProjectResponse
from langbridge.apps.api.langbridge_api.services.organization_service import OrganizationService
from langbridge.apps.api.langbridge_api.services.service_utils import is_internal_service_call


@inject
def get_current_user(request: Request) -> UserResponse:
    user = getattr(request.state, "user", None)
    if user:
        return user
    if getattr(request.state, "is_internal", False) or is_internal_service_call():
        internal_user = UserResponse(
            id=uuid.UUID(int=0),
            username="internal-service",
            email=None,
            is_active=True,
            available_organizations=[],
            available_projects=[],
        )
        request.state.user = internal_user
        request.state.username = internal_user.username
        if hasattr(request.state, "request_context"):
            request.state.request_context.user = internal_user
        return internal_user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthenticated")


@inject
def has_organization_access(
    request: Request,
    organization_id: str | None = None,  # allow explicit injection OR fallback to path_params
) -> UserResponse:
    user: UserResponse = get_current_user(request)

    # Prefer explicit param if FastAPI injected it; otherwise fallback
    org_id = organization_id or request.path_params.get("organization_id")
    if org_id is None:
        return user  # endpoint doesn't use org scoping
    if getattr(request.state, "is_internal", False) or is_internal_service_call():
        return user

    allowed_org_ids = {str(o) for o in user.available_organizations} # type: ignore
    if str(org_id) not in allowed_org_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return user


@inject
def has_project_access(
    request: Request,
    project_id: str | None = None,
) -> UserResponse:
    user: UserResponse = get_current_user(request)

    # project_id will come from query, so either accept injected param or look it up
    pid = project_id or request.query_params.get("project_id")
    if pid is None:
        return user
    if getattr(request.state, "is_internal", False) or is_internal_service_call():
        return user

    allowed_project_ids = {str(p) for p in user.available_projects}  # type: ignore
    if str(pid) not in allowed_project_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return user


@inject
def require_internal_service(request: Request) -> None:
    if getattr(request.state, "is_internal", False) or is_internal_service_call():
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@inject
async def get_organization(
    request: Request,
    organization_id: str = Path(...),
    _: UserResponse = Depends(has_organization_access),
    org_service: OrganizationService = Depends(Provide[Container.organization_service]),
) -> OrganizationResponse:
    try:
        org_uuid = uuid.UUID(str(organization_id))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid organization_id")

    org = await org_service.get_organization(org_uuid)

    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if hasattr(request.state, "request_context"):
        request.state.request_context.current_org_id = org_uuid

    return org

@inject
async def get_project(
    request: Request,
    project_id: Optional[str] = Query(None, description="Optional project filter"),
    org: OrganizationResponse = Depends(get_organization),
    _: UserResponse = Depends(has_project_access),
    org_service: OrganizationService = Depends(Provide[Container.organization_service]),
) -> ProjectResponse | None:
    if project_id is None:
        return None

    try:
        project_uuid = uuid.UUID(str(project_id))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid project_id")

    project = await org_service.get_project(project_uuid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if str(getattr(project, "organization_id", "")) != str(getattr(org, "id", "")):
        raise HTTPException(status_code=400, detail="project_id does not belong to organization_id")

    if hasattr(request.state, "request_context"):
        request.state.request_context.current_project_id = project_uuid

    return project
