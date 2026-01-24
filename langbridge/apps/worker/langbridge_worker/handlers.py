from __future__ import annotations

from typing import Callable

from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
)


HandlerFn = Callable[[MessageEnvelope], None]


def handle_message(message: MessageEnvelope) -> None:
    handler = _HANDLERS.get(message.message_type, _handle_unknown)
    handler(message)


def _handle_test(message: MessageEnvelope) -> None:
    # Placeholder handler for validation of the messaging pipeline.
    payload = message.payload
    print(f"[worker] test message received: {payload}")


def _handle_unknown(message: MessageEnvelope) -> None:
    print(
        f"[worker] no handler for message_type={message.message_type}; payload={message.payload}"
    )


_HANDLERS: dict[str, HandlerFn] = {
    "test": _handle_test,
}
