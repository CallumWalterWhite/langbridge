from typing import Type
from models.query import ModelSearchCollectionRequest

class QuerySearchValidator:
    def __init__(self, model: Type):
        self._model = model

    def validate(self, request: ModelSearchCollectionRequest) -> None:
        for filter in request.filters:
            if filter.fieldReference not in self._model.__fields__:
                raise ValueError(f"Invalid field: {filter.fieldReference}")