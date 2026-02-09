from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.job import JobEventRecord, JobRecord
from .base import AsyncBaseRepository


class JobRepository(AsyncBaseRepository[JobRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, JobRecord)

    async def get_by_id(self, id_: object) -> JobRecord | None:
        stmt = (
            select(JobRecord)
            .options(
                selectinload(JobRecord.job_events),
                selectinload(JobRecord.job_tasks),
            )
            .where(JobRecord.id == id_)
        )
        result = await self._session.scalars(stmt)
        return result.one_or_none()

    async def get_existing_ids(self, ids: set[UUID]) -> set[UUID]:
        if not ids:
            return set()
        stmt = select(JobRecord.id).where(JobRecord.id.in_(ids))
        result = await self._session.scalars(stmt)
        return set(result.all())

    def add_job_event(self, event: JobEventRecord) -> JobEventRecord:
        self._session.add(event)
        return event
