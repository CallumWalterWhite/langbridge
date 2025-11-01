from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .base import Base


def _build_connect_args(database_url: str) -> dict[str, Any]:
    """Return driver-specific connect arguments."""
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    if database_url.startswith("sqlite+aiosqlite"):
        connect_args["check_same_thread"] = False
    return connect_args


def create_engine_for_url(database_url: str, echo: bool = False) -> Engine:
    """Create SQLAlchemy engine configured for SQLite or PostgreSQL."""
    return create_engine(
        database_url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
        connect_args=_build_connect_args(database_url),
    )


def create_async_engine_for_url(database_url: str, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine configured for SQLite or PostgreSQL."""
    return create_async_engine(
        database_url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
        connect_args=_build_connect_args(database_url),
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory bound to the provided engine."""
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def create_async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build an async session factory bound to the provided async engine."""
    return async_sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def async_session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async scope around a series of operations."""
    session = session_factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def initialize_database(engine: Engine) -> None:
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
