import logging
from langbridge.packages.messaging.langbridge_messaging.handler import BaseMessageHandler
from langbridge.packages.messaging.langbridge_messaging.contracts import MessageType
from langbridge.packages.messaging.langbridge_messaging.contracts.base import TestMessagePayload


class TestMessageHandler(BaseMessageHandler):
    message_type = MessageType.TEST

    def __init__(self):
        self._logger = logging.getLogger(__name__)

    async def handle(self, payload: TestMessagePayload) -> None:
        logging.info(f"Test message: {payload.message}")
        return None