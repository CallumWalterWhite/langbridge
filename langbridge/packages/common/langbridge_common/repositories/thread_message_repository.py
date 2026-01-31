import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.threads import ThreadMessage
from .base import AsyncBaseRepository


class ThreadMessageRepository(AsyncBaseRepository[ThreadMessage]):
    """Data access helper for thread messages."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ThreadMessage)

    async def list_for_thread(self, thread_id: uuid.UUID) -> list[ThreadMessage]:
        stmt = (
            select(ThreadMessage)
            .filter(ThreadMessage.thread_id == thread_id)
            .order_by(ThreadMessage.created_at.asc())
        )
        result = await self._session.scalars(stmt)
        return list(result.all())
