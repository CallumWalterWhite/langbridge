from dependency_injector import containers, providers

from db import (
    create_async_engine_for_url,
    create_async_session_factory,
    create_engine_for_url,
    create_session_factory,
    session_scope,
)
from db.session_context import get_session
from auth.register import create_oauth_client
from repositories.connector_repository import ConnectorRepository
from repositories.environment_repository import OrganizationEnvironmentSettingRepository
from services.connector_service import ConnectorService
from services.environment_service import EnvironmentService
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
from repositories.thread_message_repository import ThreadMessageRepository
from repositories.thread_repository import ThreadRepository
from repositories.tool_call_repository import ToolCallRepository
from repositories.semantic_search_repository import SemanticVectorStoreEntryRepository
from services.auth_service import AuthService
from services.organization_service import OrganizationService
from services.agent_service import AgentService
from semantic.semantic_model_builder import SemanticModelBuilder
from services.semantic_model_service import SemanticModelService
from services.orchestrator_service import OrchestratorService
from services.thread_service import ThreadService
from services.semantic_search_sercice import SemanticSearchService
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
    async_session = providers.Factory(get_session)

    user_repository = providers.Factory(UserRepository, session=async_session)
    
    oauth_account_repository = providers.Factory(OAuthAccountRepository, session=async_session)
    organization_repository = providers.Factory(OrganizationRepository, session=async_session)
    project_repository = providers.Factory(ProjectRepository, session=async_session)
    organization_invite_repository = providers.Factory(OrganizationInviteRepository, session=async_session)
    project_invite_repository = providers.Factory(ProjectInviteRepository, session=async_session)
    connector_repository = providers.Factory(ConnectorRepository, session=async_session)
    environment_repository = providers.Factory(OrganizationEnvironmentSettingRepository, session=async_session)
    llm_connection_repository = providers.Factory(LLMConnectionRepository, session=async_session)
    semantic_model_repository = providers.Factory(SemanticModelRepository, session=async_session)
    thread_repository = providers.Factory(ThreadRepository, session=async_session)
    thread_message_repository = providers.Factory(ThreadMessageRepository, session=async_session)
    tool_call_repository = providers.Factory(ToolCallRepository, session=async_session)
    agent_definition_repository = providers.Factory(AgentRepository, session=async_session)
    semantic_vector_store_repository = providers.Factory(SemanticVectorStoreEntryRepository, session=async_session)

    environment_service = providers.Factory(
        EnvironmentService,
        repository=environment_repository,
    )
    
    organization_service = providers.Factory(
        OrganizationService,
        organization_repository=organization_repository,
        project_repository=project_repository,
        organization_invite_repository=organization_invite_repository,
        project_invite_repository=project_invite_repository,
        user_repository=user_repository,
        environment_service=environment_service,
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
        llm_repository=llm_connection_repository,
        organization_repository=organization_repository,
        project_repository=project_repository
    )

    semantic_model_builder = providers.Factory(
        SemanticModelBuilder,
        connector_service=connector_service,
    )
    
    semantic_search_service = providers.Factory(
        SemanticSearchService,
        vector_store_entry_repository=semantic_vector_store_repository,
    )

    semantic_model_service = providers.Factory(
        SemanticModelService,
        repository=semantic_model_repository,
        builder=semantic_model_builder,
        organization_repository=organization_repository,
        project_repository=project_repository,
        connector_service=connector_service,
        agent_service=agent_service,
        semantic_search_service=semantic_search_service,
    )

    thread_service = providers.Factory(
        ThreadService,
        thread_repository=thread_repository,
        thread_message_repository=thread_message_repository,
        tool_call_repository=tool_call_repository,
        project_repository=project_repository,
        organization_service=organization_service,
    )

    orchestrator_service = providers.Factory(
        OrchestratorService,
        organization_service=organization_service,
        semantic_model_service=semantic_model_service,
        connector_service=connector_service,
        agent_service=agent_service,
        thread_service=thread_service,
    )
