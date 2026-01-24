from typing import Optional
import uuid
from fastapi import Depends, HTTPException, Query, Request, Path, status
from dependency_injector.wiring import Provide, inject

from ioc.container import Container
from models.auth import UserResponse
from models.organizations import OrganizationResponse, ProjectResponse
from services.organization_service import OrganizationService


@inject
def get_current_user(request: Request) -> UserResponse:
    user = getattr(request.state, "user", None)
    if user:
        return user
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

    allowed_project_ids = {str(p) for p in user.available_projects}  # type: ignore
    if str(pid) not in allowed_project_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return user


@inject
async def get_organization(
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

    return org

@inject
async def get_project(
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

    return project