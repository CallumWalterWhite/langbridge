

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from db.semantic import SemanticModelEntry
from .base import BaseRepository


class SemanticModelRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session, SemanticModelEntry)

    def list_for_scope(self, organization_id: UUID, project_id: Optional[UUID] = None) -> List[SemanticModelEntry]:
        query = self._session.query(SemanticModelEntry).filter(SemanticModelEntry.organization_id == str(organization_id))
        if project_id:
            query = query.filter(SemanticModelEntry.project_id == project_id)
        return query.order_by(SemanticModelEntry.created_at.desc()).all()

    def get_for_scope(self, model_id: UUID, organization_id: UUID) -> Optional[SemanticModelEntry]:
        return (
            self._session.query(SemanticModelEntry)
            .filter(
                SemanticModelEntry.id == model_id,
                SemanticModelEntry.organization_id == organization_id,
            )
            .one_or_none()
        )
