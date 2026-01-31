
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.threads import Thread
from .base import AsyncBaseRepository


class ThreadRepository(AsyncBaseRepository[Thread]):
    """Data access helper for conversation threads."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Thread)

    def _select_for_user(self, user_id: uuid.UUID):
        return (
            select(Thread)
            .filter(Thread.created_by == user_id)
            .order_by(Thread.created_at.desc())
        )

    async def list_for_user(self, user_id: uuid.UUID) -> list[Thread]:
        result = await self._session.scalars(self._select_for_user(user_id))
        return list(result.all())

    async def get_for_user(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> Thread | None:
        stmt = (
            select(Thread)
            .filter(Thread.id == thread_id)
            .filter(Thread.created_by == user_id)
        )
        return await self._session.scalar(stmt)
