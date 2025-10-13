from dependency_injector import containers, providers

from db import (
    create_engine_for_url,
    create_session_factory,
    session_scope,
)
from auth.register import create_oauth_client
from repositories.connector_repository import ConnectorRepository
from services.connector_service import ConnectorService
from services.connector_schema_service import ConnectorSchemaService
from repositories.user_repository import UserRepository, OAuthAccountRepository
from repositories.organization_repository import (
    OrganizationInviteRepository,
    OrganizationRepository,
    ProjectInviteRepository,
    ProjectRepository
)
from repositories.llm_connection_repository import LLMConnectionRepository
from repositories.semantic_model_repository import SemanticModelRepository
from services.auth_service import AuthService
from services.organization_service import OrganizationService
from services.agent_service import AgentService
from services.semantic_model_builder import SemanticModelBuilder
from services.semantic_model_service import SemanticModelService
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
    llm_connection_repository = providers.Factory(LLMConnectionRepository, session=session)
    semantic_model_repository = providers.Factory(SemanticModelRepository, session=session)
    

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

    connector_schema_service = providers.Factory(
        ConnectorSchemaService,
        connector_repository=connector_repository
    )

    agent_service = providers.Factory(
        AgentService,
        repository=llm_connection_repository
    )

    semantic_model_builder = providers.Factory(
        SemanticModelBuilder,
        connector_repository=connector_repository,
        organization_repository=organization_repository,
        project_repository=project_repository,
    )

    semantic_model_service = providers.Factory(
        SemanticModelService,
        repository=semantic_model_repository,
        builder=semantic_model_builder,
        organization_repository=organization_repository,
        project_repository=project_repository,
    )
