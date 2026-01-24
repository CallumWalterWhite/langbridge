"""Worker entrypoint for async job execution."""
from __future__ import annotations

import logging
import os
import time

from redis.exceptions import RedisError

from langbridge.packages.messaging.langbridge_messaging.broker.redis_streams import (
    RedisStreamsBroker,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
)
from langbridge.apps.worker.langbridge_worker.handlers import handle_message


# TODO: Replace stub loop with real broker consumer.

def _build_test_message() -> MessageEnvelope:
    return MessageEnvelope(
        message_type="test",
        payload={"message": "hello from worker"},
    )


def run_worker(poll_interval: float = 2.0) -> None:
    logger = logging.getLogger("langbridge.worker")
    logger.info("Worker starting. Poll interval: %s seconds", poll_interval)

    run_once = os.environ.get("WORKER_RUN_ONCE", "false").lower() in {"1", "true", "yes"}
    publish_test = os.environ.get("WORKER_PUBLISH_TEST_MESSAGE", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    broker_mode = os.environ.get("WORKER_BROKER", "redis").lower()

    if broker_mode in {"none", "noop", "disabled"}:
        broker = _NoopBroker()
        logger.info("Worker broker disabled; running in noop mode")
    else:
        broker = RedisStreamsBroker()

    broker = RedisStreamsBroker()
    if publish_test:
        try:
            broker.publish(_build_test_message())
            logger.info("Published test message to %s", broker.stream)
        except RedisError as exc:
            logger.error("Failed to publish test message: %s", exc)

    while True:
        try:
            messages = broker.consume(
                timeout_ms=max(1000, int(poll_interval * 1000)),
                count=1,
            )
        except RedisError as exc:
            logger.error("Redis error: %s", exc)
            if run_once:
                return
            time.sleep(poll_interval)
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
                handle_message(envelope)
            except Exception as exc:
                logger.error("Handler error: %s", exc)
                broker.nack(message, error=str(exc))
                continue
            broker.ack(message)
        if run_once:
            logger.info("Worker run-once enabled; exiting.")
            return
        time.sleep(poll_interval)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("WORKER_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    poll_interval = float(os.environ.get("WORKER_POLL_INTERVAL", "2.0"))
    run_worker(poll_interval=poll_interval)


class _NoopBroker:
    def publish(self, message: MessageEnvelope) -> str:
        return "noop"

    def consume(self, *, timeout_ms: int, count: int):
        return []

    def ack(self, message) -> None:
        return

    def nack(self, message, *, error: str | None = None) -> None:
        return


if __name__ == "__main__":
    main()
