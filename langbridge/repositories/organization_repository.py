import uuid

from sqlalchemy.orm import Session

from db.auth import Organization, Project, OrganizationInvite, ProjectInvite, User, OrganizationUser, ProjectUser, ProjectRole, OrganizationRole
from db.connector import Connector
from .base import BaseRepository
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select, exists

class OrganizationRepository(BaseRepository):
    """Data access helper for organization entities."""

    def __init__(self, session: Session):
        super().__init__(session, Organization)

    def get_by_name(self, name: str) -> Organization | None:
        return (
            self._session.query(Organization)
            .filter(Organization.name == name)
            .one_or_none()
        )

    def list_for_user(self, user: User) -> list[Organization]:
        return (
            self._session.query(Organization)
            .join(OrganizationUser, OrganizationUser.organization_id == Organization.id)
            .filter(OrganizationUser.user_id == user.id)
            .order_by(Organization.name)
            .all()
        )

    def add_member(self, organization: Organization, user: User, role: OrganizationRole = OrganizationRole.MEMBER) -> OrganizationUser:
        """
        Upsert membership with role. Returns the OrganizationUser link.
        """
        link = (
            self._session.query(OrganizationUser)
            .filter(
                OrganizationUser.organization_id == organization.id,
                OrganizationUser.user_id == user.id,
            )
            .one_or_none()
        )
        if link:
            # update role if changed
            if link.role != role:
                link.role = role
            return link

        link = OrganizationUser(organization=organization, user=user, role=role)
        self._session.add(link)
        return link

    def remove_member(self, organization: Organization, user: User) -> None:
        link = (
            self._session.query(OrganizationUser)
            .filter(
                OrganizationUser.organization_id == organization.id,
                OrganizationUser.user_id == user.id,
            )
            .one_or_none()
        )
        if link:
            self._session.delete(link)

    def is_member(self, organization: Organization, user: User) -> bool:
        return self._session.query(
            exists().where(
                (OrganizationUser.organization_id == organization.id)
                & (OrganizationUser.user_id == user.id)
            )
        ).scalar()

    def get_member_role(self, organization: Organization, user: User) -> str | None:
        link = (
            self._session.query(OrganizationUser.role)
            .filter(
                OrganizationUser.organization_id == organization.id,
                OrganizationUser.user_id == user.id,
            )
            .one_or_none()
        )
        return link[0] if link else None


class ProjectRepository(BaseRepository):
    """Data access helper for project entities."""

    def __init__(self, session: Session):
        super().__init__(session, Project)

    def list_for_organization(self, organization_id: uuid.UUID) -> list[Project]:
        return (
            self._session.query(Project)
            .filter(Project.organization_id == organization_id)
            .order_by(Project.name)
            .all()
        )

    def get_by_name_within_org(self, organization_id: uuid.UUID, name: str) -> Project | None:
        return (
            self._session.query(Project)
            .filter(
                Project.organization_id == organization_id,
                Project.name == name,
            )
            .one_or_none()
        )

    def list_for_user(self, user: User) -> list[Project]:
        return (
            self._session.query(Project)
            .join(ProjectUser, ProjectUser.project_id == Project.id)
            .filter(ProjectUser.user_id == user.id)
            .order_by(Project.name)
            .all()
        )

    def add_member(self, project: Project, user: User, role: ProjectRole = ProjectRole.MEMBER) -> ProjectUser:
        """
        Upsert membership with role. Returns the ProjectUser link.
        """
        link = (
            self._session.query(ProjectUser)
            .filter(
                ProjectUser.project_id == project.id,
                ProjectUser.user_id == user.id,
            )
            .one_or_none()
        )
        if link:
            if link.role != role:
                link.role = role
            return link

        link = ProjectUser(project=project, user=user, role=role)
        self._session.add(link)
        return link

    def remove_member(self, project: Project, user: User) -> None:
        link = (
            self._session.query(ProjectUser)
            .filter(
                ProjectUser.project_id == project.id,
                ProjectUser.user_id == user.id,
            )
            .one_or_none()
        )
        if link:
            self._session.delete(link)

    def is_member(self, project: Project, user: User) -> bool:
        return self._session.query(
            exists().where(
                (ProjectUser.project_id == project.id)
                & (ProjectUser.user_id == user.id)
            )
        ).scalar()

    def get_member_role(self, project: Project, user: User) -> str | None:
        link = (
            self._session.query(ProjectUser.role)
            .filter(
                ProjectUser.project_id == project.id,
                ProjectUser.user_id == user.id,
            )
            .one_or_none()
        )
        return link[0] if link else None


class OrganizationInviteRepository(BaseRepository):
    """Data access helper for organization invite entities."""

    def __init__(self, session: Session):
        super().__init__(session, OrganizationInvite)

    def get_by_invitee(self, organization_id: uuid.UUID, invitee_username: str) -> OrganizationInvite | None:
        return (
            self._session.query(OrganizationInvite)
            .filter(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.invitee_username == invitee_username,
            )
            .one_or_none()
        )


class ProjectInviteRepository(BaseRepository):
    """Data access helper for project invite entities."""

    def __init__(self, session: Session):
        super().__init__(session, ProjectInvite)

    def get_by_invitee(self, project_id: uuid.UUID, invitee_id: uuid.UUID) -> ProjectInvite | None:
        return (
            self._session.query(ProjectInvite)
            .filter(
                ProjectInvite.project_id == project_id,
                ProjectInvite.invitee_id == invitee_id,
            )
            .one_or_none()
        )
