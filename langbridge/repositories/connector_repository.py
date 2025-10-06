from sqlalchemy.orm import Session
from sqlalchemy import select
from db.auth import Organization, Project
from db.connector import Connector
from db.associations import organization_connectors, project_connectors
from .base import BaseRepository


class ConnectorRepository(BaseRepository):
    """Data access helper for connector entities."""

    def __init__(self, session: Session):
        super().__init__(session, Connector)

    def get_by_name(self, name: str) -> Connector | None:
        return (
            self._session.query(Connector)
            .filter(Connector.name == name)
            .one_or_none()
        )