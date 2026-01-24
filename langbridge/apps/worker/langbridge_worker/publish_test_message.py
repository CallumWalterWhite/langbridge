"""Publish a single test message to Redis."""
from __future__ import annotations

import logging
import os

from redis.exceptions import RedisError

from langbridge.packages.messaging.langbridge_messaging.broker.redis_streams import (
    RedisStreamsBroker,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("WORKER_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("langbridge.worker.publisher")
    broker = RedisStreamsBroker()
    message = MessageEnvelope(
        message_type="test",
        payload={"message": "hello from publish_test_message"},
    )
    try:
        broker.publish(message)
        logger.info("Published test message %s to %s", message.id, broker.stream)
    except RedisError as exc:
        logger.error("Failed to publish test message: %s", exc)


if __name__ == "__main__":
    main()
