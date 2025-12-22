
import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.auth import (
    Organization,
    OrganizationInvite,
    OrganizationRole,
    OrganizationUser,
    Project,
    ProjectInvite,
    ProjectRole,
    ProjectUser,
    User,
)
from .base import AsyncBaseRepository


class OrganizationRepository(AsyncBaseRepository[Organization]):
    """Data access helper for organization entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Organization)

    async def get_by_id(self, id_: uuid.UUID) -> Organization | None:
        result = await self._session.scalars(
            select(Organization)
            .options(
                selectinload(Organization.connectors),
                selectinload(Organization.llm_connections),
                selectinload(Organization.projects),
                selectinload(Organization.user_links),
            )
            .filter(Organization.id == id_)
        )
        return result.one_or_none()

    async def get_by_name(self, name: str) -> Organization | None:
        result = await self._session.scalars(
            select(Organization)
            .options(
                selectinload(Organization.llm_connections),
                selectinload(Organization.projects),
                selectinload(Organization.user_links),
            )
            .filter(Organization.name == name)
        )
        return result.one_or_none()

    async def list_for_user(self, user: User) -> list[Organization]:
        result = await self._session.scalars(
            select(Organization)
                .options(
                    selectinload(Organization.llm_connections),
                    selectinload(Organization.projects),
                    selectinload(Organization.user_links),
                )
                .join(
                    OrganizationUser,
                    OrganizationUser.organization_id == Organization.id,
                )
                .filter(OrganizationUser.user_id == user.id)
                .order_by(Organization.name)
        )
        return list(result.all())

    async def add_member(
        self,
        organization: Organization,
        user: User,
        role: OrganizationRole = OrganizationRole.MEMBER,
    ) -> OrganizationUser:
        """Upsert membership with role. Returns the OrganizationUser link."""
        result = await self._session.scalars(
            select(OrganizationUser).filter(
                OrganizationUser.organization_id == organization.id,
                OrganizationUser.user_id == user.id,
            )
        )
        link = result.one_or_none()
        if link:
            if link.role != role:
                link.role = role
            return link

        link = OrganizationUser(organization=organization, user=user, role=role)
        self._session.add(link)
        return link

    async def remove_member(self, organization: Organization, user: User) -> None:
        result = await self._session.scalars(
            select(OrganizationUser).filter(
                OrganizationUser.organization_id == organization.id,
                OrganizationUser.user_id == user.id,
            )
        )
        link = result.one_or_none()
        if link:
            await self._session.delete(link)

    async def is_member(self, organization: Organization, user: User) -> bool:
        result = await self._session.scalar(
            select(
                exists().where(
                    (OrganizationUser.organization_id == organization.id)
                    & (OrganizationUser.user_id == user.id)
                )
            )
        )
        return bool(result)

    async def get_member_role(self, organization: Organization, user: User) -> str | None:
        result = (
            await self._session.scalars(
                select(OrganizationUser.role).filter(
                    OrganizationUser.organization_id == organization.id,
                    OrganizationUser.user_id == user.id,
                )
            )
        ).one_or_none()
        return result.value if result else None


class ProjectRepository(AsyncBaseRepository[Project]):
    """Data access helper for project entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Project)

    async def get_by_id(self, id_: uuid.UUID) -> Project | None:
        result = await self._session.scalars(
            select(Project)
            .options(
                selectinload(Project.connectors),
                selectinload(Project.llm_connections),
            )
            .filter(Project.id == id_)
        )
        return result.one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Project]:
        result = await self._session.scalars(
            select(Project)
                .filter(Project.organization_id == organization_id)
                .order_by(Project.name)
        )
        return list(result.all())

    async def get_by_name_within_org(
        self, organization_id: uuid.UUID, name: str
    ) -> Project | None:
        result = await self._session.scalars(
            select(Project).filter(
                Project.organization_id == organization_id,
                Project.name == name,
            )
        )
        return result.one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        result = await self._session.scalars(
            select(Project)
                .join(ProjectUser, ProjectUser.project_id == Project.id)
                .filter(ProjectUser.user_id == user_id)
                .order_by(Project.name)
        )
        return list(result.all())

    async def add_member(
        self,
        project: Project,
        user: User,
        role: ProjectRole = ProjectRole.MEMBER,
    ) -> ProjectUser:
        """Upsert membership with role. Returns the ProjectUser link."""
        result = await self._session.scalars(
            select(ProjectUser).filter(
                ProjectUser.project_id == project.id,
                ProjectUser.user_id == user.id,
            )
        )
        link = result.one_or_none()
        if link:
            if link.role != role:
                link.role = role
            return link

        link = ProjectUser(project=project, user=user, role=role)
        self._session.add(link)
        return link

    async def remove_member(self, project: Project, user: User) -> None:
        result = await self._session.scalars(
            select(ProjectUser).filter(
                ProjectUser.project_id == project.id,
                ProjectUser.user_id == user.id,
            )
        )
        link = result.one_or_none()
        if link:
            await self._session.delete(link)

    async def is_member(self, project: Project, user: User) -> bool:
        result = await self._session.scalar(
            select(
                exists().where(
                    (ProjectUser.project_id == project.id)
                    & (ProjectUser.user_id == user.id)
                )
            )
        )
        return bool(result)

    async def get_member_role(self, project: Project, user: User) -> str | None:
        result = (
            await self._session.scalars(
                select(ProjectUser.role).filter(
                    ProjectUser.project_id == project.id,
                    ProjectUser.user_id == user.id,
                )
            )
        ).one_or_none()
        return result.value if result else None


class OrganizationInviteRepository(AsyncBaseRepository):
    """Data access helper for organization invite entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, OrganizationInvite)

    async def get_by_invitee(
        self, organization_id: uuid.UUID, invitee_username: str
    ) -> OrganizationInvite | None:
        result = await self._session.scalars(
            select(OrganizationInvite).filter(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.invitee_username == invitee_username,
            )
        )
        return result.one_or_none()


class ProjectInviteRepository(AsyncBaseRepository):
    """Data access helper for project invite entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProjectInvite)

    async def get_by_invitee(
        self, project_id: uuid.UUID, invitee_id: uuid.UUID
    ) -> ProjectInvite | None:
        result = await self._session.scalars(
            select(ProjectInvite).filter(
                ProjectInvite.project_id == project_id,
                ProjectInvite.invitee_id == invitee_id,
            )
        )
        return result.one_or_none()
