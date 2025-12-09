"""
BigQuery connector implementation using google-cloud-bigquery.
"""


import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..base import (
    AuthError,
    ConnectorError,
    PermissionError,
    QueryValidationError,
    TimeoutError,
    SchemaInfo,
    SqlConnector,
    TableSchema,
    ColumnSchema,
    run_sync,
)

try:  # pragma: no cover - optional dependency
    from google.cloud import bigquery  # type: ignore
    from google.api_core import exceptions as gcloud_exceptions  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    bigquery = None  # type: ignore
    gcloud_exceptions = None  # type: ignore


class BigQueryConnector(SqlConnector):
    """
    BigQuery connector built on the google-cloud-bigquery client.
    """

    def __init__(
        self,
        *,
        name: str,
        config: Dict[str, Any],
        credentials: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(name=name, dialect="bigquery", logger=logger)
        self._config = config
        self._credentials = credentials
        self._driver_available = bigquery is not None
        self._client: Optional["bigquery.Client"] = None  # type: ignore[name-defined]

    def _ensure_client(self) -> "bigquery.Client":  # type: ignore[name-defined]
        if not self._driver_available:
            raise ConnectorError("google-cloud-bigquery is required for BigQuery support.")
        if self._client is None:
            project = self._config.get("project") or self._credentials.get("project")
            if not project:
                raise ConnectorError("BigQuery configuration requires a project.")
            client_kwargs: Dict[str, Any] = {"project": project}
            if "service_account_json" in self._credentials:
                client_kwargs["credentials"] = bigquery.Client.from_service_account_info(  # type: ignore[attr-defined]
                    self._credentials["service_account_json"]
                )._credentials  # type: ignore[attr-defined]
            self._client = bigquery.Client(**client_kwargs)  # type: ignore[call-arg]
        return self._client

    async def _execute_select(
        self, sql: str, params: Dict[str, Any], *, timeout_s: Optional[int]
    ) -> Tuple[List[str], List[List[Any]]]:
        client = self._ensure_client()

        job_config = bigquery.QueryJobConfig()  # type: ignore[union-attr]
        if params:
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter(name, "STRING", value)  # type: ignore[attr-defined]
                for name, value in params.items()
            ]

        def run_query():
            try:
                job = client.query(sql, job_config=job_config, timeout=timeout_s)
                result = job.result(timeout=timeout_s)
                columns = [field.name for field in result.schema]
                rows = [list(row.values()) for row in result]
                return columns, rows
            except gcloud_exceptions.Forbidden as exc:  # type: ignore[attr-defined]
                raise PermissionError(str(exc)) from exc
            except gcloud_exceptions.Unauthorized as exc:  # type: ignore[attr-defined]
                raise AuthError(str(exc)) from exc
            except gcloud_exceptions.DeadlineExceeded as exc:  # type: ignore[attr-defined]
                raise TimeoutError(str(exc)) from exc
            except gcloud_exceptions.BadRequest as exc:  # type: ignore[attr-defined]
                raise QueryValidationError(str(exc)) from exc
            except Exception as exc:
                raise ConnectorError(str(exc)) from exc

        return await run_sync(run_query)

    async def _fetch_schema(self, tables: Optional[Sequence[str]]) -> SchemaInfo:
        client = self._ensure_client()
        dataset = self._config.get("dataset")
        if not dataset:
            raise ConnectorError("BigQuery configuration requires a dataset.")

        def fetch_metadata():
            dataset_ref = client.dataset(dataset)
            table_list = tables or [table.table_id for table in client.list_tables(dataset_ref)]
            schemas: List[TableSchema] = []
            for table_id in table_list:
                table_ref = dataset_ref.table(table_id)
                table_obj = client.get_table(table_ref)
                columns = [
                    ColumnSchema(name=field.name, type=field.field_type)
                    for field in table_obj.schema
                ]
                schemas.append(TableSchema(name=table_id, columns=columns))
            return schemas

        table_schemas = await run_sync(fetch_metadata)
        return SchemaInfo(tables=table_schemas)

