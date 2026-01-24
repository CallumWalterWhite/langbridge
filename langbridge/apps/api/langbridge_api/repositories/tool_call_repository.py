import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from langbridge.apps.api.langbridge_api.db.threads import ToolCall
from .base import AsyncBaseRepository


class ToolCallRepository(AsyncBaseRepository[ToolCall]):
    """Data access helper for tool call logs."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ToolCall)

    async def list_for_message(self, message_id: uuid.UUID) -> list[ToolCall]:
        stmt = (
            select(ToolCall)
            .filter(ToolCall.message_id == message_id)
            .order_by(ToolCall.created_at.asc())
        )
        result = await self._session.scalars(stmt)
        return list(result.all())
