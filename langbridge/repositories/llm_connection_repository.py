from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.agent import LLMConnection
from .base import AsyncBaseRepository


class LLMConnectionRepository(AsyncBaseRepository[LLMConnection]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, LLMConnection)

    def _select_with_relationships(self):
        return select(LLMConnection).options(
            selectinload(LLMConnection.organizations),
            selectinload(LLMConnection.projects),
        )

    async def get_all(self) -> list[LLMConnection]:
        result = await self._session.scalars(self._select_with_relationships())
        return list(result.all())

    async def get_by_id(self, id_: object) -> LLMConnection | None:
        stmt = self._select_with_relationships().filter(LLMConnection.id == id_)
        result = await self._session.scalars(stmt)
        return result.one_or_none()
