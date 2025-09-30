from dependency_injector import containers, providers

from db import (
    create_engine_for_url,
    create_session_factory,
    session_scope,
)
from auth.register import create_oauth_client
from repositories.user_repository import UserRepository
from services.auth_service import AuthService
from config import settings


class Container(containers.DeclarativeContainer):
    """Application dependency injection container."""

    wiring_config = containers.WiringConfiguration()

    config = providers.Configuration()
    
    engine = providers.Singleton(
        create_engine_for_url,
        database_url=settings.SQLALCHEMY_DATABASE_URI,
        echo=settings.IS_LOCAL,
    )

    oauth = providers.Singleton(create_oauth_client)

    session_factory = providers.Singleton(create_session_factory, engine=engine)

    session = providers.Resource(session_scope, session_factory=session_factory)

    user_repository = providers.Factory(UserRepository, session=session)

    auth_service = providers.Factory(AuthService, user_repository=user_repository)