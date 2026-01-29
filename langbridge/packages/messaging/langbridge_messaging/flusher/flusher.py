from datetime import datetime, timedelta, timezone
import logging
from typing import List
from langbridge.packages.common.langbridge_common.db.messages import OutboxMessage
from langbridge.packages.common.langbridge_common.repositories.message_repository import MessageRepository
from ..broker.redis import MessageBroker, RedisStreams
from ..contracts.base import get_payload_model
from ..contracts.messages import (
    MessageEnvelope, 
    MessageHeaders, 
    MessageType
)
from ..contracts.stream_mapping import STREAM_MAPPING


class MessageFlusher:
    def __init__(self, 
                 message_repository: MessageRepository,
                 message_bus: MessageBroker):
        self._message_repository = message_repository
        self._message_bus = message_bus
        self._logger = logging.getLogger(__name__)
        
    async def flush_messages_by_correlation_id(self, correlation_id: str) -> List[int]:
        pending_messages: List[OutboxMessage] = await self._message_repository.get_pending_messages(correlation_id)
        sent_message_ids: List[str] = []
        self._logger.info(f"Flushing {len(pending_messages)} messages for correlation ID: {correlation_id}")
        for message_record in pending_messages:
            message_envelope = self._build_message_envelope(message_record)
            stream = self._get_stream_for_message_type(message_envelope.message_type)
            self._logger.info(f"Flushing message ID {message_record.id} to stream {stream}")
            await self._message_bus.publish(message_envelope, stream)
            sent_message_ids.append(message_record.id)
        await self._message_repository.mark_messages_as_sent(sent_message_ids)
        return sent_message_ids

    async def flush_all_messages(self, time_delay: int = 0) -> List[int]:
        timestamp_marker: datetime = datetime.now(timezone.utc) - timedelta(seconds=time_delay)
        pending_messages: List[OutboxMessage] = await self._message_repository.get_all_pending_messages(timestamp_marker)
        sent_message_ids: List[str] = []
        for message_record in pending_messages:
            message_envelope = self._build_message_envelope(message_record)
            stream = self._get_stream_for_message_type(message_envelope.message_type)
            await self._message_bus.publish(message_envelope, stream)
            sent_message_ids.append(message_record.id)
        await self._message_repository.mark_messages_as_sent(sent_message_ids)
        return sent_message_ids
    
    async def get_message_count_by_correlation_id(self, correlation_id: str) -> int:
        return await self._message_repository.count_pending_messages(correlation_id)
            
    def _build_message_envelope(self, message_record: OutboxMessage) -> MessageEnvelope:
        return MessageEnvelope(
            id=getattr(message_record, "id"),
            message_type=MessageType(getattr(message_record, "message_type")),
            payload=get_payload_model(getattr(message_record, "message_type")).model_validate(getattr(message_record, "payload")),
            headers=MessageHeaders(
                **getattr(message_record, "headers")
            ),
            created_at=message_record.created_at,
        )

    def _get_stream_for_message_type(self, message_type: MessageType) -> RedisStreams:
        stream = STREAM_MAPPING.get(message_type)
        if stream is None:
            raise ValueError(f"No stream mapping found for message type: {message_type}")
        return stream