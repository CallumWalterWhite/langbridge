from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from langbridge.packages.common.langbridge_common.db.bi import BIDashboard

from .base import AsyncBaseRepository


class DashboardRepository(AsyncBaseRepository[BIDashboard]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, BIDashboard)

    async def list_for_scope(
        self,
        organization_id: UUID,
        project_id: Optional[UUID] = None,
    ) -> list[BIDashboard]:
        query = select(BIDashboard).where(BIDashboard.organization_id == organization_id)
        if project_id is not None:
            query = query.where(BIDashboard.project_id == project_id)
        result = await self._session.scalars(
            query.order_by(BIDashboard.updated_at.desc(), BIDashboard.created_at.desc())
        )
        return list(result.all())

    async def get_for_scope(
        self,
        dashboard_id: UUID,
        organization_id: UUID,
    ) -> BIDashboard | None:
        result = await self._session.scalars(
            select(BIDashboard).where(
                BIDashboard.id == dashboard_id,
                BIDashboard.organization_id == organization_id,
            )
        )
        return result.one_or_none()
