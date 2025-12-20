import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.environment import OrganisationEnvironmentSetting
from .base import AsyncBaseRepository


class OrganizationEnvironmentSettingRepository(AsyncBaseRepository[OrganisationEnvironmentSetting]):
    """Persistence layer for organization-scoped environment settings."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, OrganisationEnvironmentSetting)

    async def get_by_key(self, organization_id: uuid.UUID, key: str) -> OrganisationEnvironmentSetting | None:
        stmt = (
            select(OrganisationEnvironmentSetting)
            .where(
                OrganisationEnvironmentSetting.organization_id == organization_id,
                OrganisationEnvironmentSetting.setting_key == key,
            )
            .limit(1)
        )
        result = await self._session.scalars(stmt)
        return result.first()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[OrganisationEnvironmentSetting]:
        stmt = select(OrganisationEnvironmentSetting).where(
            OrganisationEnvironmentSetting.organization_id == organization_id
        )
        result = await self._session.scalars(stmt)
        return list(result.all())
