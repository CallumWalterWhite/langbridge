from abc import ABC, abstractmethod
from typing import AsyncIterator

import pyarrow as pa

from .base import BaseConnector, TConfig
from .models import LangbridgeCatalog, LangbridgeSyncRequest


class SourceConnector(BaseConnector[TConfig], ABC):
    @abstractmethod
    async def get_catalog(self) -> LangbridgeCatalog:
        """Return the catalog of available resources and their schemas."""
        pass

    @abstractmethod
    async def test_connection(self) -> None:
        """Validate credentials and connectivity, raising on failure."""
        pass

    @abstractmethod
    async def fetch_resource(
        self,
        request: LangbridgeSyncRequest,
    ) -> AsyncIterator[pa.RecordBatch]:
        """Yield typed Arrow RecordBatches for the given resource and sync state."""
        pass
