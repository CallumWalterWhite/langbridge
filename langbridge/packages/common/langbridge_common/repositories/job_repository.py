from db.job import JobRecord
from sqlalchemy.ext.asyncio import AsyncSession
from .base import AsyncBaseRepository

class JobRepository(AsyncBaseRepository[JobRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, JobRecord)