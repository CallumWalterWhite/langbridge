import uuid
from typing import List

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from auth.dependencies import get_current_user
from db.auth import Organization, Project, User
from ioc import Container
from schemas import (
    InviteUserRequest,
    OrganizationCreateRequest,
    OrganizationInviteResponse,
    OrganizationResponse,
    ProjectCreateRequest,
    ProjectInviteResponse,
    ProjectResponse,
)
from services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _serialize_project(project: Project) -> ProjectResponse:
    return ProjectResponse.model_validate(
        {
            "id": project.id,
            "name": project.name,
            "organization_id": project.organization_id,
        }
    )


def _serialize_organization(organization: Organization) -> OrganizationResponse:
    project_models = [_serialize_project(project) for project in organization.projects]
    member_links = list(organization.user_links or [])
    return OrganizationResponse.model_validate(
        {
            "id": organization.id,
            "name": organization.name,
            "member_count": len(member_links),
            "projects": [proj.model_dump() for proj in project_models],
        }
    )


@router.get("", response_model=List[OrganizationResponse])
@inject
async def list_organizations(
    current_user: User = Depends(get_current_user),
    organization_service: OrganizationService = Depends(
        Provide[Container.organization_service]
    ),
) -> List[OrganizationResponse]:
    organizations = await organization_service.list_user_organizations(current_user)
    return [_serialize_organization(org) for org in organizations]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_organization(
    payload: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    organization_service: OrganizationService = Depends(
        Provide[Container.organization_service]
    ),
) -> OrganizationResponse:
    organization = await organization_service.create_organization(
        current_user,
        payload.name,
    )
    return _serialize_organization(organization)


@router.get("/{organization_id}/projects", response_model=List[ProjectResponse])
@inject
async def list_projects(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    organization_service: OrganizationService = Depends(
        Provide[Container.organization_service]
    ),
) -> List[ProjectResponse]:
    projects = await organization_service.list_projects_for_organization(
        organization_id,
        current_user,
    )
    return [_serialize_project(project) for project in projects]


@router.post(
    "/{organization_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_project(
    organization_id: uuid.UUID,
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    organization_service: OrganizationService = Depends(
        Provide[Container.organization_service]
    ),
) -> ProjectResponse:
    project = await organization_service.create_project(
        organization_id,
        current_user,
        payload.name,
    )
    return _serialize_project(project)


@router.post(
    "/{organization_id}/invites",
    response_model=OrganizationInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def invite_to_organization(
    organization_id: uuid.UUID,
    payload: InviteUserRequest,
    current_user: User = Depends(get_current_user),
    organization_service: OrganizationService = Depends(
        Provide[Container.organization_service]
    ),
) -> OrganizationInviteResponse:
    invite = await organization_service.invite_user_to_organization(
        organization_id,
        current_user,
        payload.username,
    )
    return OrganizationInviteResponse.model_validate(invite)


@router.post(
    "/{organization_id}/projects/{project_id}/invites",
    response_model=ProjectInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def invite_to_project(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: InviteUserRequest,
    current_user: User = Depends(get_current_user),
    organization_service: OrganizationService = Depends(
        Provide[Container.organization_service]
    ),
) -> ProjectInviteResponse:
    invite = await organization_service.invite_user_to_project(
        organization_id,
        project_id,
        current_user,
        payload.username,
    )
    return ProjectInviteResponse.model_validate(invite)
