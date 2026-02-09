import asyncio
import logging
from collections.abc import Callable, Iterable, Sequence

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

            await self._process_messages(messages)

    async def stop(self) -> None:
        self._stop_event.set()

    async def _process_messages(self, messages: Sequence[ReceivedMessage]) -> None:
        ack_messages: list[ReceivedMessage] = []
        nack_messages: list[tuple[ReceivedMessage, str]] = []
        job_messages: list[tuple[ReceivedMessage, JobEventMessage]] = []

        for message in messages:
            envelope = message.envelope
            if envelope.message_type != MessageType.JOB_EVENT:
                self._logger.warning(
                    "JobEventConsumer received unsupported message type %s; acking.",
                    envelope.message_type,
                )
                ack_messages.append(message)
                continue

            try:
                payload = self._parse_payload(envelope.payload)
            except Exception as exc:  # pragma: no cover - defensive guard for deserialization issues
                self._logger.error("Failed to parse job event message %s: %s", envelope.id, exc)
                nack_messages.append((message, str(exc)))
                continue

            job_messages.append((message, payload))

        if job_messages:
            acked, nacked = await self._persist_job_events(job_messages)
            ack_messages.extend(acked)
            nack_messages.extend(nacked)

        if ack_messages:
            await self._ack_messages(ack_messages)
        if nack_messages:
            await self._nack_messages(nack_messages)

    @staticmethod
    def _parse_payload(payload: BaseMessagePayload) -> JobEventMessage:
        return JobEventMessage.model_validate(payload.model_dump(mode="json"))

    async def _persist_job_events(
        self,
        messages: Sequence[tuple[ReceivedMessage, JobEventMessage]],
    ) -> tuple[list[ReceivedMessage], list[tuple[ReceivedMessage, str]]]:
        session = self._async_session_factory()
        repository = JobRepository(session=session)
        acked: list[ReceivedMessage] = []
        nacked: list[tuple[ReceivedMessage, str]] = []

        try:
            job_ids = {payload.job_id for _, payload in messages}
            existing_ids = await repository.get_existing_ids(job_ids)
            missing_ids = job_ids - existing_ids

            if missing_ids:
                for message, payload in messages:
                    if payload.job_id in missing_ids:
                        error = f"Job {payload.job_id} was not found."
                        self._logger.error("Failed to process job event message %s: %s", message.envelope.id, error)
                        nacked.append((message, error))

            valid_messages = [
                (message, payload)
                for message, payload in messages
                if payload.job_id in existing_ids
            ]

            if valid_messages:
                events = [
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
                    for _, payload in valid_messages
                ]
                session.add_all(events)
                await session.commit()
                acked.extend(message for message, _ in valid_messages)
        except Exception as exc:  # pragma: no cover - defensive guard for background loop
            await session.rollback()
            error = str(exc)
            self._logger.error("Failed to persist job event batch: %s", error)
            acked = []
            nacked = [(message, error) for message, _ in messages]
        finally:
            await session.close()

        return acked, nacked

    async def _ack_messages(self, messages: Iterable[ReceivedMessage]) -> None:
        await asyncio.gather(
            *(self._broker_client.ack(message) for message in messages),
            return_exceptions=True,
        )

    async def _nack_messages(self, messages: Iterable[tuple[ReceivedMessage, str]]) -> None:
        await asyncio.gather(
            *(self._broker_client.nack(message, error=error) for message, error in messages),
            return_exceptions=True,
        )
