from __future__ import annotations

from enum import Enum

import pyarrow as pa
from pydantic import Field

from .base import _BaseModel
from .config import ConnectorSyncStrategy


class FieldType(str, Enum):
    """Logical field types, each with a deterministic PyArrow mapping."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    BINARY = "binary"
    JSON = "json"

    def to_arrow(self) -> pa.DataType:
        """Return the concrete PyArrow data type for this logical type."""
        mapping: dict[FieldType, pa.DataType] = {
            FieldType.STRING: pa.string(),
            FieldType.INTEGER: pa.int64(),
            FieldType.FLOAT: pa.float64(),
            FieldType.BOOLEAN: pa.bool_(),
            FieldType.TIMESTAMP: pa.timestamp("us", tz="UTC"),
            FieldType.DATE: pa.date32(),
            FieldType.BINARY: pa.binary(),
            FieldType.JSON: pa.string(),
        }
        return mapping[self]

    @classmethod
    def from_arrow(cls, dtype: pa.DataType) -> FieldType:
        """Map a PyArrow data type back to the closest logical field type."""
        if pa.types.is_boolean(dtype):
            return cls.BOOLEAN
        if pa.types.is_integer(dtype):
            return cls.INTEGER
        if pa.types.is_floating(dtype) or pa.types.is_decimal(dtype):
            return cls.FLOAT
        if pa.types.is_timestamp(dtype):
            return cls.TIMESTAMP
        if pa.types.is_date(dtype):
            return cls.DATE
        if pa.types.is_binary(dtype) or pa.types.is_large_binary(dtype):
            return cls.BINARY
        if pa.types.is_string(dtype) or pa.types.is_large_string(dtype):
            return cls.STRING
        if (
            pa.types.is_struct(dtype)
            or pa.types.is_list(dtype)
            or pa.types.is_large_list(dtype)
            or pa.types.is_map(dtype)
        ):
            return cls.JSON
        return cls.STRING


class LangbridgeField(_BaseModel):
    name: str = Field(..., description="The name of the field")
    description: str = Field(..., description="A brief description of the field")
    type: FieldType = Field(..., description="The data type of the field")
    required: bool = Field(..., description="Whether the field is required (non-nullable)")

    def to_arrow_field(self) -> pa.Field:
        return pa.field(self.name, self.type.to_arrow(), nullable=not self.required)


class LangbridgeResource(_BaseModel):
    name: str = Field(..., description="The name of the resource")
    description: str = Field(..., description="A brief description of the resource")
    namespace: str = Field(..., description="The namespace or schema the resource lives in")
    primary_key: list[str] = Field(..., description="Fields that uniquely identify a record")
    cursor_field: str | None = Field(None, description="Field used for incremental sync cursoring")
    fields: list[LangbridgeField] = Field(..., description="Fields available on this resource")

    def to_arrow_schema(self) -> pa.Schema:
        return pa.schema([f.to_arrow_field() for f in self.fields])


class LangbridgeCatalog(_BaseModel):
    name: str = Field(..., description="The name of the catalog")
    description: str = Field(..., description="A brief description of the catalog")
    resources: list[LangbridgeResource] = Field(..., description="Resources available through this connector")

    def get_resource(self, name: str) -> LangbridgeResource | None:
        for resource in self.resources:
            if resource.name == name:
                return resource
        return None


class LangbridgeSyncRequest(_BaseModel):
    resource: str = Field(..., description="The name of the resource to fetch")
    strategy: ConnectorSyncStrategy = Field(..., description="The synchronization strategy to apply")
    cursor_value: str | None = Field(None, description="Cursor value from the previous sync run, used for incremental strategies")
    batch_size: int = Field(1000, ge=1, description="Number of records per yielded batch")


class LangbridgeQueryRequest(_BaseModel):
    query: str = Field(..., description="The SQL query to execute against the data source")
