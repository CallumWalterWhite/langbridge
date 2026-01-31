from typing import Optional
import uuid
from langbridge.packages.common.langbridge_common.repositories.semantic_search_repository import SemanticVectorStoreEntryRepository
from langbridge.packages.common.langbridge_common.db.semantic import SemanticVectorStoreEntry

class SemanticSearchService:
    def __init__(self,
            vector_store_entry_repository: SemanticVectorStoreEntryRepository):
        self._vector_store_entry_repository = vector_store_entry_repository
        
    async def create_semantic_vector_entry(self,
            connector_id: uuid.UUID,
            name: str,
            description: Optional[str],
            vector_store_type: str,
            metadata_filters: Optional[str],
            organization_id: uuid.UUID,
            project_id: Optional[uuid.UUID] = None,
            sematic_vector_store_entry_id: Optional[uuid.UUID] = None,
        ) -> SemanticVectorStoreEntry:
        entry = SemanticVectorStoreEntry(
            id=sematic_vector_store_entry_id or uuid.uuid4(),
            connector_id=connector_id,
            name=name,
            description=description,
            vector_store_type=vector_store_type,
            metadata_filters=metadata_filters,
            organization_id=organization_id,
            project_id=project_id,
        )
        await self._vector_store_entry_repository.add(entry)
        return entry
    
    async def add_vector_to_semantic(
        self,
        vector_entry: SemanticVectorStoreEntry,
        semantic_id: uuid.UUID
    ) -> None:
        await self._vector_store_entry_repository.add_to_semantic_model(
            semantic_model_id=semantic_id,
            vector_entry_id=vector_entry.id,
        )