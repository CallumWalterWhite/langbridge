import json
import uuid
from typing import Any, Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..contracts.connectors import ConnectorDTO
from ..db.connector import Connector
from ..interfaces.connectors import IConnectorStore
from .base import AsyncBaseRepository


class ConnectorRepository(AsyncBaseRepository[Connector]):
    """Data access helper for connector entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Connector)

    def _with_relationships(self):
        return [
            selectinload(Connector.organizations),
            selectinload(Connector.projects),
        ]

    def _select_with_relationships(self):
        return select(Connector).options(*self._with_relationships())

    async def get_by_name(self, name: str) -> Connector | None:
        stmt = self._select_with_relationships().filter(Connector.name == name)
        result = await self._session.scalars(stmt)
        return result.one_or_none()

    async def get_by_id(self, id_: object) -> Connector | None:
        stmt = self._select_with_relationships().filter(Connector.id == id_)
        result = await self._session.scalars(stmt)
        return result.one_or_none()

    async def get_all(self) -> list[Connector]:
        stmt = self._select_with_relationships()
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def get_by_ids(self, connector_ids: list[uuid.UUID]) -> list[Connector]:
        stmt = self._select_with_relationships().filter(Connector.id.in_(connector_ids))
        result = await self._session.scalars(stmt)
        return list(result.all())
    
class ConnectorStore(IConnectorStore):
    def __init__(self, repository: ConnectorRepository):
        self._repository = repository

    @staticmethod
    def _to_dto(connector: Connector) -> ConnectorDTO:
        raw_config = connector.config_json
        config: Optional[dict[str, Any]] = None
        if isinstance(raw_config, (str, bytes)):
            try:
                parsed = json.loads(raw_config)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                config = cast(dict[str, Any], parsed)
        elif isinstance(raw_config, dict):
            config = raw_config

        org_id = None
        if getattr(connector, "organizations", None):
            org_id = connector.organizations[0].id
        elif getattr(connector, "organization_id", None):
            org_id = connector.organization_id
        if org_id is None:
            raise ValueError(f"Connector {connector.id} has no associated organization.")

        project_id = None
        if getattr(connector, "projects", None):
            project_id = connector.projects[0].id

        return ConnectorDTO(
            id=connector.id,
            name=connector.name,
            description=connector.description,
            version="",
            label=connector.name,
            icon="",
            connector_type=connector.connector_type,
            organization_id=org_id,
            project_id=project_id,
            config=config,
        )

    async def get_by_name(self, name: str) -> ConnectorDTO | None:
        connector = await self._repository.get_by_name(name)
        if connector is None:
            return None
        return self._to_dto(connector)
    
    async def get_by_id(self, connector_id: uuid.UUID) -> ConnectorDTO | None:
        connector = await self._repository.get_by_id(connector_id)
        if connector is None:
            return None
        return self._to_dto(connector)

    async def get_by_ids(self, connector_ids: list[uuid.UUID]) -> list[ConnectorDTO]:
        connectors = await self._repository.get_by_ids(connector_ids)
        return [self._to_dto(connector) for connector in connectors]
    
    async def get_all(self) -> list[ConnectorDTO]:
        connectors = await self._repository.get_all()
        return [self._to_dto(connector) for connector in connectors]
