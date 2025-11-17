from dependency_injector import containers, providers

from db import (
    async_session_scope,
    create_async_engine_for_url,
    create_async_session_factory,
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
from repositories.agent_repository import AgentRepository
from repositories.thread_repository import ThreadRepository
from services.auth_service import AuthService
from services.organization_service import OrganizationService
from services.agent_service import AgentService
from semantic.semantic_model_builder import SemanticModelBuilder
from services.semantic_model_service import SemanticModelService
from services.orchestrator_service import OrchestratorService
from services.thread_service import ThreadService
from config import settings


class Container(containers.DeclarativeContainer):
    """Application dependency injection container."""

    wiring_config = containers.WiringConfiguration()

    config = providers.Configuration()
    
    engine = providers.Singleton(
        create_engine_for_url,
        database_url=settings.SQLALCHEMY_DATABASE_URI,
        echo=settings.IS_LOCAL,
        pool_size=settings.SQLALCHEMY_POOL_SIZE,
        max_overflow=settings.SQLALCHEMY_MAX_OVERFLOW,
        pool_timeout=settings.SQLALCHEMY_POOL_TIMEOUT,
    )

    async_engine = providers.Singleton(
        create_async_engine_for_url,
        database_url=settings.SQLALCHEMY_ASYNC_DATABASE_URI,
        echo=settings.IS_LOCAL,
        pool_size=settings.SQLALCHEMY_POOL_SIZE,
        max_overflow=settings.SQLALCHEMY_MAX_OVERFLOW,
        pool_timeout=settings.SQLALCHEMY_POOL_TIMEOUT,
    )

    oauth = providers.Singleton(create_oauth_client)

    session_factory = providers.Singleton(create_session_factory, engine=engine)
    async_session_factory = providers.Singleton(
        create_async_session_factory,
        engine=async_engine,
    )

    session = providers.Resource(session_scope, session_factory=session_factory)
    async_session = providers.Resource(
        async_session_scope,
        session_factory=async_session_factory,
    )

    user_repository = providers.Factory(UserRepository, session=async_session)
    
    oauth_account_repository = providers.Factory(OAuthAccountRepository, session=async_session)
    organization_repository = providers.Factory(OrganizationRepository, session=async_session)
    project_repository = providers.Factory(ProjectRepository, session=async_session)
    organization_invite_repository = providers.Factory(OrganizationInviteRepository, session=async_session)
    project_invite_repository = providers.Factory(ProjectInviteRepository, session=async_session)
    connector_repository = providers.Factory(ConnectorRepository, session=async_session)
    llm_connection_repository = providers.Factory(LLMConnectionRepository, session=async_session)
    semantic_model_repository = providers.Factory(SemanticModelRepository, session=async_session)
    thread_repository = providers.Factory(ThreadRepository, session=async_session)
    agent_definition_repository = providers.Factory(AgentRepository, session=async_session)

    organization_service = providers.Factory(
        OrganizationService,
        organization_repository=organization_repository,
        project_repository=project_repository,
        organization_invite_repository=organization_invite_repository,
        project_invite_repository=project_invite_repository,
        user_repository=user_repository,
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
        agent_definition_repository=agent_definition_repository,
        llm_repository=llm_connection_repository
    )

    semantic_model_builder = providers.Factory(
        SemanticModelBuilder,
        connector_service=connector_service,
    )

    semantic_model_service = providers.Factory(
        SemanticModelService,
        repository=semantic_model_repository,
        builder=semantic_model_builder,
        organization_repository=organization_repository,
        project_repository=project_repository,
        connector_service=connector_service,
        agent_service=agent_service,
    )

    orchestrator_service = providers.Factory(
        OrchestratorService,
        organization_service=organization_service,
        semantic_model_service=semantic_model_service,
        connector_service=connector_service,
        agent_service=agent_service
    )

    thread_service = providers.Factory(
        ThreadService,
        thread_repository=thread_repository,
        project_repository=project_repository,
        organization_service=organization_service,
    )
