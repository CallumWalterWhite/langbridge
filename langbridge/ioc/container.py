from dependency_injector import containers, providers

from db import (
    create_engine_for_url,
    create_session_factory,
    session_scope,
)
from auth.register import create_oauth_client
from repositories.connector_repository import ConnectorRepository
from services.connector_service import ConnectorService
from repositories.user_repository import UserRepository, OAuthAccountRepository
from repositories.organization_repository import (
    OrganizationInviteRepository,
    OrganizationRepository,
    ProjectInviteRepository,
    ProjectRepository,
)
from services.auth_service import AuthService
from services.organization_service import OrganizationService
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
    
    oauth_account_repository = providers.Factory(OAuthAccountRepository, session=session)
    organization_repository = providers.Factory(OrganizationRepository, session=session)
    project_repository = providers.Factory(ProjectRepository, session=session)
    organization_invite_repository = providers.Factory(OrganizationInviteRepository, session=session)
    project_invite_repository = providers.Factory(ProjectInviteRepository, session=session)
    connector_repository = providers.Factory(ConnectorRepository, session=session)
    

    organization_service = providers.Factory(
        OrganizationService,
        organization_repository=organization_repository,
        project_repository=project_repository,
        organization_invite_repository=organization_invite_repository,
        project_invite_repository=project_invite_repository,
        user_repository=user_repository,
        session=session,
    )

    auth_service = providers.Factory(
        AuthService,
        user_repository=user_repository,
        oauth_account_repository=oauth_account_repository,
        oauth=oauth,
        organization_service=organization_service,
    )
    
    connector_service = providers.Factory(
        ConnectorService,
        connector_repository=connector_repository,
        organization_repository=organization_repository,
        project_repository=project_repository
    )
