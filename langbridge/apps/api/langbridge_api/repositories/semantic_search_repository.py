from .base import AsyncBaseRepository
from langbridge.apps.api.langbridge_api.db.semantic import SemanticVectorStoreEntry
from sqlalchemy.future import select
from typing import List
from uuid import UUID
from langbridge.apps.api.langbridge_api.db.associations import vector_entry_semantic

class SemanticVectorStoreEntryRepository(AsyncBaseRepository):
    """Repository for managing SemanticVectorStoreEntry entities."""
    
    def __init__(self, session):
        super().__init__(session, SemanticVectorStoreEntry)

    async def get_by_semantic_model_id(
        self,
        semantic_model_id: UUID,
    ) -> List[SemanticVectorStoreEntry]:
        """Retrieve all SemanticVectorStoreEntry entities for a given semantic model ID. via vector_entry_semantic association table."""
        stmt = (
            select(SemanticVectorStoreEntry)
            .join(vector_entry_semantic)
            .where(vector_entry_semantic.c.semantic_model_id == semantic_model_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
    
    async def delete_by_semantic_model_id(
        self,
        semantic_model_id: UUID,
    ) -> None:
        """Delete all SemanticVectorStoreEntry entities for a given semantic model ID via vector_entry_semantic association table."""
        stmt = (
            select(SemanticVectorStoreEntry)
            .join(vector_entry_semantic)
            .where(vector_entry_semantic.c.semantic_model_id == semantic_model_id)
        )
        result = await self._session.execute(stmt)
        entries = result.scalars().all()
        for entry in entries:
            await self._session.delete(entry)
        
    async def get_by_namespace(
        self,
        namespace: str,
    ) -> List[SemanticVectorStoreEntry]:
        """Retrieve all SemanticVectorStoreEntry entities for a given namespace."""
        stmt = (
            select(SemanticVectorStoreEntry)
            .where(SemanticVectorStoreEntry.name == namespace)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
    
    async def add_to_semantic_model(
        self,
        semantic_model_id: UUID,
        vector_entry_id: UUID,
    ) -> None:
        """Associate a SemanticVectorStoreEntry with a semantic model via the association table."""
        stmt = vector_entry_semantic.insert().values(
            semantic_model_id=semantic_model_id,
            vector_entry_id=vector_entry_id
        )
        await self._session.execute(stmt)