from abc import ABC
from typing import Any, List, Optional

from schemas.base import _Base


class ConnectorConfigEntrySchema(_Base):
    field: str
    value: Optional[Any] = None
    label: Optional[str] = None
    required: bool
    default: Optional[str] = None
    description: str
    type: str
    value_list: Optional[List[str]] = None


class ConnectorConfigSchema(_Base):
    name: str
    description: str
    version: str
    label: str
    icon: str
    connector_type: str
    config: List[ConnectorConfigEntrySchema]

class BaseConnectorConfigSchemaFactory(ABC):
    type: str

    @classmethod
    def create(cls, config: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(**config)