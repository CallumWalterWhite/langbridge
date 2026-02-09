from typing import Protocol
import uuid

from ..contracts.semantic import SemanticModelRecordResponse


class ISemanticModelStore(Protocol):
    async def get_by_id(self, model_id: uuid.UUID) -> SemanticModelRecordResponse | None: ...
    async def get_by_ids(
        self,
        model_ids: list[uuid.UUID],
    ) -> list[SemanticModelRecordResponse]: ...
