from __future__ import annotations


class MessageFlusher:
    def __init__(self, *, message_repository, message_bus) -> None:
        self.message_repository = message_repository
        self.message_bus = message_bus

    async def flush(self) -> None:
        return None


__all__ = ["MessageFlusher"]
