import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.agent import AgentDefinition
from .base import AsyncBaseRepository


class AgentRepository(AsyncBaseRepository[AgentDefinition]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AgentDefinition)