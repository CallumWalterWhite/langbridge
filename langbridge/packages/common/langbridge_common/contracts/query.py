from typing import Any
from langbridge.packages.common.langbridge_common.contracts.base import _Base


class ModelSearchRequest(_Base):
    fieldReference: str
    operator: str
    value: Any

class ModelSearchCollectionRequest(_Base):
    filters: list[ModelSearchRequest]
    modelReference: str
    limit: int
    offset: int