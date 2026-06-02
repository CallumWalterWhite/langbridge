from __future__ import annotations

from pydantic import Field

from ...models import ConnectorConfig


class FileConnectorConfig(ConnectorConfig):
    """Configuration for the file connector.

    The connector exposes every supported data file in ``path`` as a resource
    named after the file stem. Supported formats: CSV, Parquet, JSON.
    """

    path: str = Field(..., description="Directory containing the data files to expose")
