from __future__ import annotations

from typing import Any

from dependency_injector import containers, providers

from langbridge.apps.api.langbridge_api.auth.register import create_oauth_client
from langbridge.packages.common.langbridge_common.config import Settings, settings
from langbridge.packages.common.langbridge_common.db import (
    create_async_engine_for_url,
    create_async_session_factory,
    create_engine_for_url,
    create_session_factory,
    session_scope,
)
from langbridge.packages.common.langbridge_common.db.session_context import get_session
from langbridge.packages.common.langbridge_common.repositories.agent_repository import AgentRepository
from langbridge.packages.common.langbridge_common.repositories.connector_repository import ConnectorRepository
from langbridge.packages.common.langbridge_common.repositories.environment_repository import OrganizationEnvironmentSettingRepository
from langbridge.packages.common.langbridge_common.repositories.llm_connection_repository import LLMConnectionRepository
from langbridge.packages.common.langbridge_common.repositories.organization_repository import (
    OrganizationInviteRepository,
    OrganizationRepository,
    ProjectInviteRepository,
    ProjectRepository,
)
from langbridge.packages.common.langbridge_common.repositories.semantic_model_repository import SemanticModelRepository
from langbridge.packages.common.langbridge_common.repositories.semantic_search_repository import SemanticVectorStoreEntryRepository
from langbridge.packages.common.langbridge_common.repositories.thread_message_repository import ThreadMessageRepository
from langbridge.packages.common.langbridge_common.repositories.thread_repository import ThreadRepository
from langbridge.packages.common.langbridge_common.repositories.tool_call_repository import ToolCallRepository
from langbridge.packages.common.langbridge_common.repositories.user_repository import OAuthAccountRepository, UserRepository
from langbridge.packages.common.langbridge_common.repositories.message_repository import MessageRepository
from langbridge.packages.semantic.langbridge_semantic.semantic_model_builder import SemanticModelBuilder
from langbridge.apps.api.langbridge_api.services.agent_service import AgentService
from langbridge.apps.api.langbridge_api.services.auth_service import AuthService
from langbridge.apps.api.langbridge_api.services.connector_schema_service import ConnectorSchemaService
from langbridge.apps.api.langbridge_api.services.connector_service import ConnectorService
from langbridge.apps.api.langbridge_api.services.environment_service import EnvironmentService
from langbridge.apps.api.langbridge_api.services.internal_api_client import InternalApiClient
from langbridge.apps.api.langbridge_api.services.organization_service import OrganizationService
from langbridge.apps.api.langbridge_api.services.orchestrator_service import OrchestratorService
from langbridge.apps.api.langbridge_api.services.message.message_serivce import MessageService
from langbridge.apps.api.langbridge_api.services.request_context_provider import RequestContextProvider
from langbridge.apps.api.langbridge_api.services.semantic import (
    SemanticModelService,
    SemanticQueryService,
    SemanticSearchService,
)
from langbridge.apps.api.langbridge_api.services.thread_service import ThreadService
from langbridge.packages.messaging.langbridge_messaging.broker.redis import RedisBroker
from langbridge.packages.messaging.langbridge_messaging.flusher.flusher import MessageFlusher
from langbridge.apps.api.langbridge_api.request_context import get_request_context


class Container(containers.DeclarativeContainer):
    """Application dependency injection container."""

    wiring_config = containers.WiringConfiguration()

    config = providers.Configuration()

    engine = providers.Singleton(
        create_engine_for_url,
        database_url=config.database.url,
        echo=config.database.echo,
        pool_size=config.database.pool_size,
        max_overflow=config.database.max_overflow,
        pool_timeout=config.database.pool_timeout,
    )

    async_engine = providers.Singleton(
        create_async_engine_for_url,
        database_url=config.database.async_url,
        echo=config.database.echo,
        pool_size=config.database.pool_size,
        max_overflow=config.database.max_overflow,
        pool_timeout=config.database.pool_timeout,
    )

    oauth = providers.Singleton(create_oauth_client)

    internal_api_client = providers.Factory(
        InternalApiClient,
        base_url=settings.BACKEND_URL,
        service_token=settings.SERVICE_USER_SECRET,
    )
    request_context = providers.Factory(get_request_context)
    request_context_provider = providers.Factory(
        RequestContextProvider,
        request_context=request_context,
    )

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
    message_repository = providers.Factory(MessageRepository, session=async_session)
    message_broker = providers.Singleton(RedisBroker)

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
    
    message_service = providers.Factory(
        MessageService,
        message_repository=message_repository,
        request_context_provider=request_context_provider,
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
        emvironment_service=environment_service
    )

    semantic_query_service = providers.Factory(
        SemanticQueryService,
        semantic_model_service=semantic_model_service,
        connector_service=connector_service
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
        message_service=message_service,
    )

    message_flusher = providers.Factory(
        MessageFlusher,
        message_repository=message_repository,
        message_bus=message_broker,
    )


def _build_config(settings_obj: Settings) -> dict[str, Any]:
    return {
        "database": {
            "url": settings_obj.SQLALCHEMY_DATABASE_URI,
            "async_url": settings_obj.SQLALCHEMY_ASYNC_DATABASE_URI,
            "echo": settings_obj.IS_LOCAL,
            "pool_size": settings_obj.SQLALCHEMY_POOL_SIZE,
            "max_overflow": settings_obj.SQLALCHEMY_MAX_OVERFLOW,
            "pool_timeout": settings_obj.SQLALCHEMY_POOL_TIMEOUT,
        },
    }


def build_container(settings_obj: Settings = settings) -> Container:
    """Build a Container with settings bound to configuration providers."""
    container = Container()
    container.config.from_dict(_build_config(settings_obj))
    return container
