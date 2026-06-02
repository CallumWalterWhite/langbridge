from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import ClassVar, Generic, TypeVar

from .models import ConnectorConfig, ConnectorConfigSchema

TConfig = TypeVar("TConfig", bound=ConnectorConfig)


class BaseConnector(ABC, Generic[TConfig]):
    """Base class for every connector.

    A connector is constructed with a typed, validated configuration object.
    The configuration *schema* is exposed as a classmethod so that it can be
    inspected for discovery and UI rendering before any instance is created.

    Connectors that hold expensive resources (connection pools, file handles)
    should override :meth:`connect` / :meth:`disconnect`. The class is also an
    async context manager, so ``async with connector:`` manages that lifecycle.
    """

    #: Stable key used to register and look the connector up in the registry.
    key: ClassVar[str] = ""

    def __init__(self, config: TConfig) -> None:
        self.config: TConfig = config

    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> ConnectorConfigSchema:
        """Describe the configuration fields this connector requires."""
        raise NotImplementedError

    async def connect(self) -> None:
        """Acquire any resources needed before use. Safe to call repeatedly."""
        return None

    async def disconnect(self) -> None:
        """Release any resources held by the connector."""
        return None

    async def __aenter__(self) -> BaseConnector[TConfig]:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.disconnect()
