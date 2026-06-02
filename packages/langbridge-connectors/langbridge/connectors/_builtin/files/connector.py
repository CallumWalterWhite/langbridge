"""File connector — exposes local CSV / Parquet / JSON files as resources.

Files are self-describing, so the file's native Arrow schema is the source of
truth: :meth:`fetch_resource` yields the file's native record batches and
:meth:`get_catalog` reports those types via :meth:`FieldType.from_arrow`.
"""
import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.json as pajson
import pyarrow.parquet as pq

from ...errors import ConnectorConnectionError, ResourceNotFoundError
from ...models import (
    ConnectorCapabilities,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorPluginMetadata,
    ConnectorSyncStrategy,
    FieldType,
    LangbridgeCatalog,
    LangbridgeField,
    LangbridgeResource,
    LangbridgeSyncRequest,
)
from ...source import SourceConnector
from .config import FileConnectorConfig

_SUFFIX_FORMATS: dict[str, str] = {
    ".csv": "csv",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".json": "json",
    ".jsonl": "json",
    ".ndjson": "json",
}


def _read_schema(path: Path, file_format: str) -> pa.Schema:
    if file_format == "parquet":
        return pq.read_schema(path)
    if file_format == "csv":
        reader = pacsv.open_csv(path)
        try:
            return reader.schema
        finally:
            reader.close()
    return pajson.read_json(path).schema


def _read_batches(path: Path, file_format: str, batch_size: int) -> list[pa.RecordBatch]:
    if file_format == "parquet":
        return list(pq.ParquetFile(path).iter_batches(batch_size=batch_size))
    if file_format == "csv":
        table = pacsv.read_csv(path)
    else:
        table = pajson.read_json(path)
    return table.to_batches(max_chunksize=batch_size)


class FileConnector(SourceConnector[FileConnectorConfig]):
    """Connector that exposes data files in a directory as queryable resources."""

    key = "files"

    @classmethod
    def get_config_schema(cls) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="Files",
            description="Expose local CSV, Parquet and JSON files as queryable resources.",
            version="1.0.0",
            config=[
                ConnectorConfigEntrySchema(
                    field="path",
                    label="Directory",
                    required=True,
                    description="Directory containing the data files to expose.",
                    type="string",
                ),
            ],
            plugin_metadata=ConnectorPluginMetadata(
                default_sync_strategy=ConnectorSyncStrategy.FULL_REFRESH,
                capabilities=ConnectorCapabilities(
                    supports_synced_datasets=True,
                    supports_preview=True,
                    supports_federated_execution=True,
                ),
            ),
        )

    async def test_connection(self) -> None:
        if not Path(self.config.path).is_dir():
            raise ConnectorConnectionError(
                f"File connector path is not a directory: {self.config.path}"
            )

    async def get_catalog(self) -> LangbridgeCatalog:
        resources: list[LangbridgeResource] = []
        for name, (path, file_format) in self._discover().items():
            schema = await asyncio.to_thread(_read_schema, path, file_format)
            fields = [
                LangbridgeField(
                    name=field.name,
                    description=f"{field.type} column",
                    type=FieldType.from_arrow(field.type),
                    required=not field.nullable,
                )
                for field in schema
            ]
            resources.append(
                LangbridgeResource(
                    name=name,
                    description=f"{file_format} file '{path.name}'",
                    namespace="",
                    primary_key=[],
                    cursor_field=None,
                    fields=fields,
                )
            )
        return LangbridgeCatalog(
            name="files",
            description=f"Data files in '{self.config.path}'",
            resources=resources,
        )

    async def fetch_resource(
        self,
        request: LangbridgeSyncRequest,
    ) -> AsyncIterator[pa.RecordBatch]:
        discovered = self._discover()
        if request.resource not in discovered:
            raise ResourceNotFoundError(request.resource)
        path, file_format = discovered[request.resource]
        batches = await asyncio.to_thread(
            _read_batches, path, file_format, request.batch_size
        )
        for batch in batches:
            yield batch

    def _discover(self) -> dict[str, tuple[Path, str]]:
        """Map resource name -> (file path, format) for every supported file."""
        root = Path(self.config.path)
        if not root.is_dir():
            raise ConnectorConnectionError(
                f"File connector path is not a directory: {self.config.path}"
            )
        discovered: dict[str, tuple[Path, str]] = {}
        for entry in sorted(root.iterdir()):
            if not entry.is_file():
                continue
            file_format = _SUFFIX_FORMATS.get(entry.suffix.lower())
            if file_format is not None:
                discovered[entry.stem] = (entry, file_format)
        return discovered
