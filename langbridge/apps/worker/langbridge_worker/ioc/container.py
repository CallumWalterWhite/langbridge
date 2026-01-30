from __future__ import annotations

from typing import Any

from dependency_injector import containers, providers

from langbridge.apps.api.langbridge_api.db import (
    create_async_engine_for_url,
    create_async_session_factory,
)
from langbridge.apps.api.langbridge_api.db.session_context import get_session
from langbridge.packages.common.langbridge_common.config import Settings, settings
from langbridge.packages.common.langbridge_common.repositories.message_repository import MessageRepository
from langbridge.packages.messaging.langbridge_messaging.broker.redis import RedisBroker
from langbridge.packages.messaging.langbridge_messaging.flusher.flusher import MessageFlusher


class WorkerContainer(containers.DeclarativeContainer):
    """Worker dependency injection container."""

    wiring_config = containers.WiringConfiguration()

    config = providers.Configuration()

    async_engine = providers.Singleton(
        create_async_engine_for_url,
        database_url=config.database.async_url,
        echo=config.database.echo,
        pool_size=config.database.pool_size,
        max_overflow=config.database.max_overflow,
        pool_timeout=config.database.pool_timeout,
    )

    async_session_factory = providers.Singleton(
        create_async_session_factory,
        engine=async_engine,
    )

    async_session = providers.Factory(get_session)

    message_repository = providers.Factory(MessageRepository, session=async_session)
    message_broker = providers.Singleton(
        RedisBroker,
        stream=settings.REDIS_WORKER_STREAM,
        group=settings.REDIS_WORKER_CONSUMER_GROUP,
    )
    message_flusher = providers.Factory(
        MessageFlusher,
        message_repository=message_repository,
        message_bus=message_broker,
    )


def build_config(settings_obj: Settings) -> dict[str, Any]:
    return {
        "database": {
            "async_url": settings_obj.SQLALCHEMY_ASYNC_DATABASE_URI,
            "echo": settings_obj.IS_LOCAL,
            "pool_size": settings_obj.SQLALCHEMY_POOL_SIZE,
            "max_overflow": settings_obj.SQLALCHEMY_MAX_OVERFLOW,
            "pool_timeout": settings_obj.SQLALCHEMY_POOL_TIMEOUT,
        }
    }


def create_container() -> WorkerContainer:
    container = WorkerContainer()
    container.config.from_dict(build_config(settings))
    return container
