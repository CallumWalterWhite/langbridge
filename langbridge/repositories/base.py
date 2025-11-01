from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]):
        self._session = session
        self._model = model

    def add(self, instance: ModelT) -> ModelT:
        self._session.add(instance)
        return instance

    def delete(self, instance: ModelT) -> None:
        self._session.delete(instance)

    def get_by_id(self, id_: object) -> ModelT | None:
        return self._session.get(self._model, id_)

    def get_all(self) -> list[ModelT]:
        return list(self._session.scalars(select(self._model)).all())


class AsyncBaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]):
        self._session = session
        self._model = model

    def add(self, instance: ModelT) -> ModelT:
        """Add instance to the session; caller manages flush/commit."""
        self._session.add(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self._session.delete(instance)

    async def get_by_id(self, id_: object) -> ModelT | None:
        return await self._session.get(self._model, id_)

    async def get_all(self) -> list[ModelT]:
        result = await self._session.scalars(select(self._model))
        return list(result.all())

    async def commit(self) -> None:
        await self._session.commit()

    async def flush(self) -> None:
        await self._session.flush()
