from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from langbridge.packages.common.langbridge_common.db.job import (
    JobEventRecord,
    JobEventVisibility as JobEventRecordVisibility,
)
from langbridge.packages.common.langbridge_common.interfaces.agent_events import (
    AgentEventVisibility,
)
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.messaging.langbridge_messaging.broker.base import (
    MessageBroker,
    ReceivedMessage,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.base import MessageType
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.event import (
    JobEventMessage,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.base import BaseMessagePayload


class JobEventConsumer:
    """Consumes job event messages from Redis and persists them to the jobs table."""

    def __init__(
        self,
        *,
        broker_client: MessageBroker,
        async_session_factory: Callable[[], AsyncSession],
        poll_interval_seconds: float = 1.0,
        batch_size: int = 20,
        logger: logging.Logger | None = None,
    ) -> None:
        self._broker_client = broker_client
        self._async_session_factory = async_session_factory
        self._poll_interval_seconds = max(0.1, poll_interval_seconds)
        self._batch_size = max(1, batch_size)
        self._logger = logger or logging.getLogger(__name__)
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                messages = await self._broker_client.consume(
                    timeout_ms=max(1000, int(self._poll_interval_seconds * 1000)),
                    count=self._batch_size,
                )
            except RedisError as exc:
                self._logger.warning("Job event consumer Redis error: %s", exc)
                await asyncio.sleep(self._poll_interval_seconds)
                continue
            except Exception as exc:  # pragma: no cover - defensive guard for stream deserialization errors
                self._logger.error("Job event consumer failed to read stream: %s", exc)
                await asyncio.sleep(self._poll_interval_seconds)
                continue

            if not messages:
                continue

            for message in messages:
                await self._process_message(message)

    async def stop(self) -> None:
        self._stop_event.set()
        await self._broker_client.close()

    async def _process_message(self, message: ReceivedMessage) -> None:
        envelope = message.envelope
        if envelope.message_type != MessageType.JOB_EVENT:
            self._logger.warning(
                "JobEventConsumer received unsupported message type %s; acking.",
                envelope.message_type,
            )
            await self._broker_client.ack(message)
            return

        try:
            payload = self._parse_payload(envelope.payload)
            await self._persist_job_event(payload)
        except Exception as exc:  # pragma: no cover - defensive guard for background loop
            self._logger.error("Failed to process job event message %s: %s", envelope.id, exc)
            await self._broker_client.nack(message, error=str(exc))
            return

        await self._broker_client.ack(message)

    @staticmethod
    def _parse_payload(payload: BaseMessagePayload) -> JobEventMessage:
        return JobEventMessage.model_validate(payload.model_dump(mode="json"))

    async def _persist_job_event(self, payload: JobEventMessage) -> None:
        session = self._async_session_factory()
        repository = JobRepository(session=session)
        try:
            job = await repository.get_by_id(payload.job_id)
            if job is None:
                raise ValueError(f"Job {payload.job_id} was not found.")

            repository.add_job_event(
                JobEventRecord(
                    job_id=payload.job_id,
                    event_type=payload.event_type,
                    details={
                        "visibility": payload.visibility,
                        "message": payload.message,
                        "source": payload.source or "agent-runtime",
                        "details": payload.details or {},
                    },
                    visibility=(
                        JobEventRecordVisibility.public
                        if payload.visibility == AgentEventVisibility.public.value
                        else JobEventRecordVisibility.internal
                    ),
                )
            )
            await repository.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
