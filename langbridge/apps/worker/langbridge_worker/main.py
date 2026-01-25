"""Worker entrypoint for async job execution."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Sequence

from redis.exceptions import RedisError

from langbridge.packages.messaging.langbridge_messaging.broker.redis import RedisBroker
from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
)
from langbridge.packages.common.langbridge_common.monitoring import start_metrics_server
from .handlers import WorkerMessageHandler

async def run_worker(poll_interval: float = 2.0) -> None:
    logger = logging.getLogger("langbridge.worker")
    logger.info("Worker starting. Poll interval: %s seconds", poll_interval)

    run_once = os.environ.get("WORKER_RUN_ONCE", "false").lower() in {"1", "true", "yes"}
    broker_mode = os.environ.get("WORKER_BROKER", "redis").lower()

    worker_handler = WorkerMessageHandler()

    if broker_mode in {"none", "noop", "disabled"}:
        broker = _NoopBroker()
        logger.info("Worker broker disabled; running in noop mode")
    else:
        broker = RedisBroker()

    try:
        while True:
            try:
                messages = await broker.consume(
                    timeout_ms=max(1000, int(poll_interval * 1000)),
                    count=1,
                )
            except RedisError as exc:
                logger.error("Redis error: %s", exc)
                if run_once:
                    return
                await asyncio.sleep(poll_interval)
                continue

            if not messages:
                logger.info("Worker idle: awaiting jobs")
            for message in messages:
                envelope = message.envelope
                logger.info(
                    "Received message %s (%s)",
                    envelope.id,
                    envelope.message_type,
                )
                try:
                    new_messages: Sequence[MessageEnvelope] | None = await worker_handler.handle_message(envelope)
                    if new_messages:
                        for new_message in new_messages:
                            await broker.publish(new_message)
                except Exception as exc:
                    logger.error("Handler error: %s", exc)
                    await broker.nack(message, error=str(exc))
                    continue
                await broker.ack(message)
            if run_once:
                logger.info("Worker run-once enabled; exiting.")
                return
            await asyncio.sleep(poll_interval)
    finally:
        await broker.close()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("WORKER_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    poll_interval = float(os.environ.get("WORKER_POLL_INTERVAL", "2.0"))
    metrics_port = int(os.environ.get("WORKER_METRICS_PORT", "9101"))
    start_metrics_server(metrics_port)
    asyncio.run(run_worker(poll_interval=poll_interval))


class _NoopBroker:
    async def publish(self, message: MessageEnvelope) -> str:
        return "noop"

    async def consume(self, *, timeout_ms: int, count: int):
        return []

    async def ack(self, message) -> None:
        return

    async def nack(self, message, *, error: str | None = None) -> None:
        return

    async def close(self) -> None:
        return


if __name__ == "__main__":
    main()
