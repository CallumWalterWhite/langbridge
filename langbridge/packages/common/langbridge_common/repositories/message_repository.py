import datetime
from typing import List
from sqlalchemy import select
from ..db.messages import OutboxMessage, MessageStatus
from sqlalchemy.ext.asyncio import AsyncSession
from .base import AsyncBaseRepository

class MessageRepository(AsyncBaseRepository[OutboxMessage]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, OutboxMessage)
        
    async def get_pending_messages(self, correlation_id: str) -> List[OutboxMessage]:
        query = select(OutboxMessage).filter(OutboxMessage.correlation_id == correlation_id and OutboxMessage.status == MessageStatus.not_sent)
        return await self._session.execute(query)
    
    async def get_all_pending_messages(self, timestamp_marker: datetime = None) -> List[OutboxMessage]:
        query = select(OutboxMessage).filter(OutboxMessage.status == MessageStatus.not_sent)
        if timestamp_marker:
            query = query.filter(OutboxMessage.created_at <= timestamp_marker)
        result = await self._session.execute(query)
        return result.scalars().all()
    
    async def mark_message_as_sent(self, message_id: str) -> None:
        query = select(OutboxMessage).filter(OutboxMessage.id == message_id)
        result = await self._session.execute(query)
        message = result.scalar_one_or_none()
        if message:
            message.status = MessageStatus.sent
            
    async def mark_messages_as_sent(self, message_ids: List[str]) -> None:
        query = select(OutboxMessage).filter(OutboxMessage.id.in_(message_ids))
        result = await self._session.execute(query)
        messages = result.scalars().all()
        for message in messages:
            message.status = MessageStatus.sent