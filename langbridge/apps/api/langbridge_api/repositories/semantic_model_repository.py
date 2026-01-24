

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from langbridge.apps.api.langbridge_api.db.semantic import SemanticModelEntry, SemanticVectorStoreEntry
from .base import AsyncBaseRepository


class SemanticModelRepository(AsyncBaseRepository[SemanticModelEntry]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SemanticModelEntry)

    async def list_for_scope(self, organization_id: UUID, project_id: Optional[UUID] = None) -> List[SemanticModelEntry]:
        query = select(SemanticModelEntry).filter(SemanticModelEntry.organization_id == organization_id)
        if project_id:
            query = query.filter(SemanticModelEntry.project_id == project_id)
        result = await self._session.scalars(query.order_by(SemanticModelEntry.created_at.desc()))
        return list(result.all())

    async def get_for_scope(self, model_id: UUID, organization_id: UUID) -> Optional[SemanticModelEntry]:
        return (
            await (
                self._session.scalars(select(SemanticModelEntry).filter(
                    SemanticModelEntry.id == model_id,
                    SemanticModelEntry.organization_id == organization_id,
                ))
            )
        ).one_or_none()

class SemanticVectorStoreRepository(AsyncBaseRepository[SemanticVectorStoreEntry]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SemanticVectorStoreEntry)

    async def list_for_scope(self, organization_id: UUID, project_id: Optional[UUID] = None) -> List[SemanticVectorStoreEntry]:
        query = select(SemanticVectorStoreEntry).filter(SemanticVectorStoreEntry.organization_id == organization_id)
        if project_id:
            query = query.filter(SemanticVectorStoreEntry.project_id == project_id)
        result = await self._session.scalars(query.order_by(SemanticVectorStoreEntry.created_at.desc()))
        return list(result.all())

    async def get_for_scope(self, store_id: UUID, organization_id: UUID) -> Optional[SemanticVectorStoreEntry]:
        return (
            await (
                self._session.scalars(select(SemanticVectorStoreEntry).filter(
                    SemanticVectorStoreEntry.id == store_id,
                    SemanticVectorStoreEntry.organization_id == organization_id,
                ))
            )
        ).one_or_none()
    