from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.connector import Connector
from .base import AsyncBaseRepository


class ConnectorRepository(AsyncBaseRepository):
    """Data access helper for connector entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Connector)

    def _with_relationships(self):
        return [
            selectinload(Connector.organizations),
            selectinload(Connector.projects),
        ]

    def _select_with_relationships(self):
        return select(Connector).options(*self._with_relationships())

    async def get_by_name(self, name: str) -> Connector | None:
        stmt = self._select_with_relationships().filter(Connector.name == name)
        result = await self._session.scalars(stmt)
        return result.one_or_none()

    async def get_by_id(self, id_: object) -> Connector | None:
        stmt = self._select_with_relationships().filter(Connector.id == id_)
        result = await self._session.scalars(stmt)
        return result.one_or_none()

    async def get_all(self) -> list[Connector]:
        stmt = self._select_with_relationships()
        result = await self._session.scalars(stmt)
        return list(result.all())
