from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.auth import InviteStatus, Organization, OrganizationInvite, OrganizationRole, Project, ProjectInvite, ProjectRole, User
from errors.application_errors import (
    BusinessValidationError,
    PermissionDeniedBusinessValidationError,
    ResourceNotFound,
)
from repositories.organization_repository import (
    OrganizationInviteRepository,
    OrganizationRepository,
    ProjectInviteRepository,
    ProjectRepository,
)
from repositories.user_repository import UserRepository


class OrganizationService:
    """Domain logic for managing organizations, projects, and invitations."""

    def __init__(
        self,
        organization_repository: OrganizationRepository,
        project_repository: ProjectRepository,
        organization_invite_repository: OrganizationInviteRepository,
        project_invite_repository: ProjectInviteRepository,
        user_repository: UserRepository,
        session: Session,
    ) -> None:
        self._organization_repository = organization_repository
        self._project_repository = project_repository
        self._organization_invite_repository = organization_invite_repository
        self._project_invite_repository = project_invite_repository
        self._user_repository = user_repository
        self._session = session

    def list_user_organizations(self, user: User) -> list[Organization]:
        return self._organization_repository.list_for_user(user)

    def ensure_default_workspace_for_user(self, user: User) -> tuple[Organization, Project]:
        default_name = user.username.strip()
        if not default_name:
            raise BusinessValidationError("User username cannot be empty for workspace creation")
        
        default_name = default_name.strip() + "'s Workspace"

        organization = self._organization_repository.get_by_name(default_name)
        project: Project | None = None

        if organization is None:
            organization = Organization(name=default_name)
            self._organization_repository.add(organization)
        if not self._organization_repository.is_member(organization, user):
            self._organization_repository.add_member(organization, user, OrganizationRole.OWNER)

        project = self._project_repository.get_by_name_within_org(organization.id, default_name)
        if project is None:
            project = Project(name=default_name, organization=organization)
            self._project_repository.add(project)
        if not self._project_repository.is_member(project, user):
            self._project_repository.add_member(project, user, ProjectRole.OWNER)

        return organization, project

    def create_organization(self, owner: User, name: str) -> Organization:
        normalized_name = name.strip()
        if not normalized_name:
            raise BusinessValidationError("Organization name is required")

        existing = self._organization_repository.get_by_name(normalized_name)
        if existing is not None:
            raise BusinessValidationError("An organization with this name already exists")

        organization = Organization(name=normalized_name)
        self._organization_repository.add(organization)
        self._organization_repository.add_member(organization, owner)
        return organization

    def create_project(self, organization_id: uuid.UUID, requester: User, name: str) -> Project:
        organization = self._organization_repository.get_by_id(organization_id)
        if organization is None:
            raise ResourceNotFound("Organization not found")

        if not self._organization_repository.is_member(organization, requester):
            raise PermissionDeniedBusinessValidationError("You are not a member of this organization")

        normalized_name: str = name.strip()
        if not normalized_name:
            raise BusinessValidationError("Project name is required")

        if self._project_repository.get_by_name_within_org(organization_id, normalized_name):
            raise BusinessValidationError("A project with this name already exists in the organization")

        project = Project(name=normalized_name, organization=organization)
        self._project_repository.add(project)
        self._project_repository.add_member(project, requester)
        return project

    def invite_user_to_organization(self, organization_id: uuid.UUID, inviter: User, invitee_username: str) -> OrganizationInvite:
        organization = self._organization_repository.get_by_id(organization_id)
        if organization is None:
            raise ResourceNotFound("Organization not found")

        if not self._organization_repository.is_member(organization, inviter):
            raise PermissionDeniedBusinessValidationError("You are not a member of this organization")

        normalized_username = invitee_username.strip()
        if not normalized_username:
            raise BusinessValidationError("Invitee username is required")

        invitee = self._user_repository.get_by_username(normalized_username)
        if invitee is None:
            raise ResourceNotFound("No user exists with that username")

        if self._organization_repository.is_member(organization, invitee):
            raise BusinessValidationError("That user is already a member of this organization")

        existing = self._organization_invite_repository.get_by_invitee(organization.id, normalized_username)
        timestamp = datetime.now(timezone.utc)

        if existing:
            existing.status = InviteStatus.ACCEPTED
            existing.responded_at = timestamp
            self._organization_repository.add_member(organization, invitee)
            return existing

        invite = OrganizationInvite(
            organization=organization,
            inviter=inviter,
            invitee_username=normalized_username,
            status=InviteStatus.ACCEPTED,
            responded_at=timestamp,
        )
        self._organization_invite_repository.add(invite)
        self._organization_repository.add_member(organization, invitee)
        return invite

    def invite_user_to_project(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        inviter: User,
        invitee_username: str,
    ) -> ProjectInvite:
        organization = self._organization_repository.get_by_id(organization_id)
        if organization is None:
            raise ResourceNotFound("Organization not found")

        project = self._project_repository.get_by_id(project_id)
        if project is None or project.organization_id != organization.id:
            raise ResourceNotFound("Project not found in this organization")

        if not self._organization_repository.is_member(organization, inviter):
            raise PermissionDeniedBusinessValidationError("You are not a member of this organization")

        normalized_username = invitee_username.strip()
        if not normalized_username:
            raise BusinessValidationError("Invitee username is required")

        invitee = self._user_repository.get_by_username(normalized_username)
        if invitee is None:
            raise ResourceNotFound("No user exists with that username")

        if not self._organization_repository.is_member(organization, invitee):
            raise BusinessValidationError("User must join the organization before being added to a project")

        if self._project_repository.is_member(project, invitee):
            raise BusinessValidationError("That user is already a member of this project")

        existing = self._project_invite_repository.get_by_invitee(project.id, invitee.id)
        timestamp = datetime.now(timezone.utc)

        if existing:
            existing.status = InviteStatus.ACCEPTED
            existing.responded_at = timestamp
            self._project_repository.add_member(project, invitee)
            return existing

        invite = ProjectInvite(
            project=project,
            inviter=inviter,
            invitee=invitee,
            status=InviteStatus.ACCEPTED,
            responded_at=timestamp,
        )
        self._project_invite_repository.add(invite)
        self._project_repository.add_member(project, invitee)
        return invite

    def list_projects_for_organization(self, organization_id: uuid.UUID, user: User) -> list[Project]:
        organization = self._organization_repository.get_by_id(organization_id)
        if organization is None:
            raise ResourceNotFound("Organization not found")

        if not self._organization_repository.is_member(organization, user):
            raise PermissionDeniedBusinessValidationError("You are not a member of this organization")

        return self._project_repository.list_for_organization(organization_id)
