from typing import Callable, Type
from langbridge.packages.messaging.langbridge_messaging.handler import BaseMessageHandler


class DependencyResolver:
    def resolve(self, handler: Type[BaseMessageHandler]) -> BaseMessageHandler:
        return handler()