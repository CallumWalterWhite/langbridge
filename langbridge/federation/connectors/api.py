import logging
import math
import time
from typing import Any

import duckdb
import pyarrow as pa

from langbridge.connectors.base.connector import ApiConnector
from langbridge.federation.connectors.base import RemoteExecutionResult, RemoteSource, SourceCapabilities
from langbridge.federation.models.plans import SourceSubplan
from langbridge.federation.models.virtual_dataset import TableStatistics, VirtualTableBinding


def _records_to_arrow(records: list[dict[str, Any]]) -> pa.Table:
    if not records:
        return pa.table({})
    return pa.Table.from_pylist(records)


class ApiConnectorRemoteSource(RemoteSource):
    def __init__(
        self,
        *,
        source_id: str,
        connector: ApiConnector,
        bindings: list[VirtualTableBinding],
        logger: logging.Logger | None = None,
    ) -> None:
        self.source_id = source_id
        self._connector = connector
        self._bindings = {binding.table_key: binding for binding in bindings}
        self._logger = logger or logging.getLogger(__name__)

    def capabilities(self) -> SourceCapabilities:
        return SourceCapabilities(
            pushdown_filter=True,
            pushdown_projection=True,
            pushdown_aggregation=True,
            pushdown_limit=True,
            pushdown_join=True,
        )

    def dialect(self) -> str:
        return "duckdb"

    async def execute(self, subplan: SourceSubplan) -> RemoteExecutionResult:
        self._logger.debug("Executing remote subplan stage=%s source=%s", subplan.stage_id, self.source_id)
        started = time.perf_counter()
        connection = duckdb.connect(database=":memory:")
        try:
            await self._register_bindings(connection=connection)
            sql = (subplan.sql or "").strip()
            if not sql:
                binding = self._require_binding(subplan.table_key)
                sql = f"SELECT * FROM {self._qualified_relation_name(binding)}"
            result = connection.execute(sql)
            table = result.fetch_arrow_table()
            return RemoteExecutionResult(
                table=table if isinstance(table, pa.Table) else pa.table({}),
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
        finally:
            connection.close()

    async def estimate_table_stats(self, binding: VirtualTableBinding) -> TableStatistics:
        table_binding = self._require_binding(binding.table_key)
        if table_binding.stats is not None:
            return table_binding.stats

        try:
            arrow_table = await self._fetch_binding_table(table_binding)
            row_count = float(arrow_table.num_rows)
            bytes_per_row = 128.0
            if arrow_table.num_rows > 0:
                bytes_per_row = max(1.0, float(arrow_table.nbytes) / float(arrow_table.num_rows))
            return TableStatistics(row_count_estimate=row_count, bytes_per_row=bytes_per_row)
        except Exception:
            table_name = self._qualified_relation_name(table_binding)
            self._logger.warning("Falling back to heuristic stats for source=%s table=%s", self.source_id, table_name)
            return TableStatistics(row_count_estimate=1_000_000.0, bytes_per_row=128.0)

    async def _register_bindings(
        self,
        *,
        connection: duckdb.DuckDBPyConnection,
    ) -> None:
        for index, binding in enumerate(self._bindings.values()):
            arrow_table = await self._fetch_binding_table(binding)
            temp_name = self._temporary_relation_name(index=index, binding=binding)
            connection.register(temp_name, arrow_table)
            if binding.schema_name:
                connection.execute(
                    f"CREATE SCHEMA IF NOT EXISTS {self._quote_identifier(binding.schema_name)}"
                )
            connection.execute(
                "CREATE OR REPLACE VIEW "
                f"{self._qualified_relation_name(binding)} AS SELECT * FROM {self._quote_identifier(temp_name)}"
            )

    async def _fetch_binding_table(self, binding: VirtualTableBinding) -> pa.Table:
        resource_name = self._resource_name(binding)
        extract_result = await self._connector.extract_resource(resource_name=resource_name)
        return _records_to_arrow(list(extract_result.records or []))

    def _require_binding(self, table_key: str) -> VirtualTableBinding:
        binding = self._bindings.get(table_key)
        if binding is None and len(self._bindings) == 1:
            return next(iter(self._bindings.values()))
        if binding is None:
            raise KeyError(f"API source '{self.source_id}' has no binding for table '{table_key}'.")
        return binding

    @staticmethod
    def _resource_name(binding: VirtualTableBinding) -> str:
        descriptor = getattr(binding, "dataset_descriptor", None)
        descriptor_source = (
            dict(descriptor.source or {})
            if descriptor is not None and isinstance(descriptor.source, dict)
            else {}
        )
        metadata = binding.metadata if isinstance(binding.metadata, dict) else {}
        resource_name = str(
            descriptor_source.get("resource")
            or metadata.get("api_resource")
            or ""
        ).strip()
        if not resource_name:
            raise ValueError(f"API binding '{binding.table_key}' is missing dataset source.resource.")
        return resource_name

    @staticmethod
    def _temporary_relation_name(*, index: int, binding: VirtualTableBinding) -> str:
        normalized = str(binding.table_key or binding.table or f"binding_{index}").replace(".", "_")
        return f"api_binding_{index}_{normalized}"

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return '"' + str(identifier or "api_dataset").replace('"', '""') + '"'

    @classmethod
    def _qualified_relation_name(cls, binding: VirtualTableBinding) -> str:
        relation = cls._quote_identifier(binding.table)
        if binding.schema_name:
            return f"{cls._quote_identifier(binding.schema_name)}.{relation}"
        return relation


def estimate_bytes(*, rows: float | None, bytes_per_row: float) -> float | None:
    if rows is None:
        return None
    if rows < 0:
        return None
    return float(math.ceil(rows * bytes_per_row))
