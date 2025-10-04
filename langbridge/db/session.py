from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sqlalchemy.ext.asyncio import AsyncSession

from .base import Base
from . import auth  # noqa: F401 - ensure models are registered with metadata


def create_engine_for_url(database_url: str, echo: bool = False) -> Engine:
    """Create SQLAlchemy engine configured for SQLite or PostgreSQL."""
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        database_url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory bound to the provided engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)



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


def initialize_database(engine: Engine) -> None:
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
