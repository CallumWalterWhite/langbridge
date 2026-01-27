from datetime import datetime, timedelta, timezone
from typing import List
from langbridge.packages.common.langbridge_common.db.messages import OutboxMessage
from langbridge.packages.common.langbridge_common.repositories.message_repository import MessageRepository
from ..broker.redis import MessageBroker
from ..contracts.base import get_payload_model
from ..contracts.messages import MessageEnvelope, MessageHeaders, MessageType


class MessageFlusher:
    def __init__(self, 
                 message_repository: MessageRepository,
                 message_bus: MessageBroker):
        self._message_repository = message_repository
        self._message_bus = message_bus
        
    async def flush_messages_by_correlation_id(self, correlation_id: str) -> List[int]:
        pending_messages: List[OutboxMessage] = await self._message_repository.get_pending_messages(correlation_id)
        sent_message_ids: List[str] = []
        for message_record in pending_messages:
            message_envelope = self._build_message_envelope(message_record)
            await self._message_bus.publish(message_envelope)
            sent_message_ids.append(message_record.id)
        await self._message_repository.mark_messages_as_sent(sent_message_ids)
        return sent_message_ids

    async def flush_all_messages(self, time_delay: int = 0) -> List[int]:
        timestamp_marker: datetime = datetime.now(timezone.utc) - timedelta(seconds=time_delay)
        pending_messages: List[OutboxMessage] = await self._message_repository.get_all_pending_messages(timestamp_marker)
        sent_message_ids: List[str] = []
        for message_record in pending_messages:
            message_envelope = self._build_message_envelope(message_record)
            await self._message_bus.publish(message_envelope)
            sent_message_ids.append(message_record.id)
        await self._message_repository.mark_messages_as_sent(sent_message_ids)
        return sent_message_ids
            
    def _build_message_envelope(self, message_record: OutboxMessage) -> MessageEnvelope:
        return MessageEnvelope(
            id=message_record.id,
            message_type=MessageType(message_record.message_type),
            payload=get_payload_model(message_record.message_type).model_validate(message_record.payload),
            headers=MessageHeaders(
                **message_record.headers
            ),
            created_at=message_record.created_at,
        )
