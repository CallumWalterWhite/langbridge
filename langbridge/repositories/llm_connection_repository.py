import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.associations import organization_llm_connections, project_llm_connections
from db.agent import LLMConnection
from .base import AsyncBaseRepository


class LLMConnectionRepository(AsyncBaseRepository[LLMConnection]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, LLMConnection)

    def _select_with_relationships(self):
        return select(LLMConnection).options(
            selectinload(LLMConnection.organizations),
            selectinload(LLMConnection.projects),
        )

    async def get_all(self,
                      organization_id: uuid.UUID | None = None,
                      project_id: uuid.UUID | None = None
                      ) -> list[LLMConnection]:
        stmt = self._select_with_relationships()
        if organization_id:
            stmt = stmt.join(
                organization_llm_connections,
                organization_llm_connections.c.llm_connection_id == LLMConnection.id,
            ).filter(organization_llm_connections.c.organization_id == organization_id)
        if project_id:
            stmt = stmt.join(
                project_llm_connections,
                project_llm_connections.c.llm_connection_id == LLMConnection.id,
            ).filter(project_llm_connections.c.project_id == project_id)
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def get_by_id(self, id_: object) -> LLMConnection | None:
        stmt = self._select_with_relationships().filter(LLMConnection.id == id_)
        result = await self._session.scalars(stmt)
        return result.one_or_none()

    async def add_to_organization(self, organization_id: uuid.UUID, llm_connection_id: uuid.UUID):
        stmt = organization_llm_connections.insert().values(
            organization_id=organization_id,
            llm_connection_id=llm_connection_id
        )
        await self._session.execute(stmt)
        
    async def add_to_project(self, project_id: uuid.UUID, llm_connection_id: uuid.UUID):
        stmt = project_llm_connections.insert().values(
            project_id=project_id,
            llm_connection_id=llm_connection_id
        )
        await self._session.execute(stmt)
