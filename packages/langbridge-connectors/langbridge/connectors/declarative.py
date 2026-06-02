from abc import abstractmethod
from typing import Any, AsyncIterator

import pyarrow as pa

from .base import TConfig
from .errors import ResourceNotFoundError
from .models import LangbridgeResource, LangbridgeSyncRequest
from .source import SourceConnector


class DeclarativeConnector(SourceConnector[TConfig]):
    """
    Base for REST/HTTP connectors that declare resources via get_catalog()
    and produce raw records page-by-page via fetch_batches().

    Subclasses implement:
      - get_catalog()      → declare available resources and their typed schemas
      - fetch_batches()    → yield pages of raw dicts from the upstream API

    The base handles Arrow conversion using the declared resource schema,
    so subclasses never deal with PyArrow directly.
    """

    @abstractmethod
    async def fetch_batches(
        self,
        resource: LangbridgeResource,
        cursor_value: str | None,
        batch_size: int,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Yield pages of raw records for a resource, respecting cursor state."""
        pass

    async def fetch_resource(
        self,
        request: LangbridgeSyncRequest,
    ) -> AsyncIterator[pa.RecordBatch]:
        catalog = await self.get_catalog()
        resource = catalog.get_resource(request.resource)
        if resource is None:
            raise ResourceNotFoundError(request.resource)

        schema = resource.to_arrow_schema()
        async for page in self.fetch_batches(resource, request.cursor_value, request.batch_size):
            if page:
                yield pa.RecordBatch.from_pylist(page, schema=schema)
