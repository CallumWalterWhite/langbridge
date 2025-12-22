import uuid
from typing import List, Optional

from db.agent import LLMConnection, AgentDefinition
from errors.application_errors import AuthorizationError, BusinessValidationError
from db.auth import Organization
from repositories.organization_repository import OrganizationRepository, ProjectRepository
from services.service_utils import internal_service, is_internal_service_call
from models.auth import UserResponse
from repositories.agent_repository import AgentRepository
from models.llm_connections import (
    LLMConnectionCreate,
    LLMConnectionResponse,
    LLMConnectionSecretResponse,
    LLMConnectionTest,
    LLMConnectionUpdate,
    LLMProvider,
)
from .user_auth_provider import UserAuthorizedProvider
from models.agents import AgentDefinitionCreate, AgentDefinitionResponse, AgentDefinitionUpdate
from repositories.llm_connection_repository import LLMConnectionRepository
from utils.llm.llm_tester import LLMConnectionTester


class AgentService:
    def __init__(self,
                 agent_definition_repository: AgentRepository, 
                 llm_repository: LLMConnectionRepository,
                 organization_repository: OrganizationRepository,
                 project_repository: ProjectRepository
                 ) -> None:
        self._llm_repository = llm_repository
        self._agent_definition_repository = agent_definition_repository
        self._organization_repository = organization_repository
        self._project_repository = project_repository
        self._tester = LLMConnectionTester()

    async def create_llm_connection(
        self,
        connection: LLMConnectionCreate,
        current_user: UserResponse
    ) -> LLMConnectionResponse:
        if current_user is None:
            raise BusinessValidationError("User must be authenticated to create LLM connections")
        
        if not UserAuthorizedProvider.organization_has_access(current_user, connection.organization_id):
            raise AuthorizationError("User does not have access to the specified organization")
        
        if connection.project_id and not UserAuthorizedProvider.project_has_access(current_user, connection.project_id):
            raise AuthorizationError("User does not have access to the specified project")
        
        test_result = self._tester.test_connection(
            provider=connection.provider,
            api_key=connection.api_key,
            model=connection.model,
            configuration=connection.configuration,
        )

        if not test_result["success"]:
            raise BusinessValidationError(
                f"Connection test failed: {test_result['message']}"
            )

        new_connection = LLMConnection(
            id=uuid.uuid4(),
            provider=connection.provider,
            api_key=connection.api_key,
            model=connection.model,
            is_active=True,
            configuration=connection.configuration,
            name=connection.name,
            description=connection.description,
        )

        self._llm_repository.add(new_connection)
        
        if connection.organization_id is None:
            raise BusinessValidationError("Organization ID must be provided")
            
        organization = await self._organization_repository.get_by_id(
            connection.organization_id
        )
        if not organization:
            raise BusinessValidationError("Organization not found")
        organization.llm_connections.append(new_connection)
        
        if connection.project_id:
            project = await self._project_repository.get_by_id(connection.project_id)
            if not project:
                raise BusinessValidationError("Project not found")
            project.llm_connections.append(new_connection)
        
        return LLMConnectionResponse.model_validate(new_connection)

    async def list_llm_connections(self,
                                   current_user: UserResponse,
                                   organization_id: Optional[uuid.UUID] = None,
                                   project_id: Optional[uuid.UUID] = None
                                   ) -> List[LLMConnectionResponse]:
        if current_user is None:
            raise BusinessValidationError("User must be authenticated to list LLM connections")
        if organization_id and not UserAuthorizedProvider.organization_has_access(current_user, organization_id):
            raise AuthorizationError("User does not have access to the specified organization")
        if project_id and not UserAuthorizedProvider.project_has_access(current_user, project_id):
            raise AuthorizationError("User does not have access to the specified project")
        
        connections = await self._llm_repository.get_all(
            organization_id=organization_id,
            project_id=project_id
        )
        return [LLMConnectionResponse.model_validate(conn) for conn in connections]

    @internal_service
    async def list_llm_connection_secrets(self) -> List[LLMConnectionSecretResponse]:
        connections = await self._llm_repository.get_all()
        return [LLMConnectionSecretResponse.model_validate(conn) for conn in connections]

    @internal_service
    async def get_llm_connection(
        self,
        connection_id: uuid.UUID,
        current_user: Optional[UserResponse] = None,
    ) -> Optional[LLMConnectionResponse]:
        connection: LLMConnection | None = await self._llm_repository.get_by_id(connection_id)
        if not connection:
            return None
        
        self.__check_authorized(current_user, connection)
        return LLMConnectionResponse.model_validate(connection)

    async def update_llm_connection(
        self,
        current_user: UserResponse,
        connection_id: uuid.UUID,
        connection_update: LLMConnectionUpdate,
    ) -> Optional[LLMConnectionResponse]:
        current_connection: Optional[LLMConnection] = await self._llm_repository.get_by_id(connection_id)
        if not current_connection:
            return None
        self.__check_authorized(current_user, current_connection)

        if connection_update.api_key:
            provider_value = (
                current_connection.provider.value
                if hasattr(current_connection.provider, "value")
                else current_connection.provider
            )
            schema_provider = LLMProvider(provider_value)

            test_result = self._tester.test_connection(
                provider=schema_provider,
                api_key=connection_update.api_key,
                model=str(
                    connection_update.model
                    or getattr(current_connection.model, "value", current_connection.model)
                ),
                configuration=(
                    connection_update.configuration
                    if connection_update.configuration is not None
                    else dict(current_connection.configuration)
                    if isinstance(current_connection.configuration, dict)
                    else {}
                ),
            )

            if not test_result["success"]:
                raise ValueError(f"Connection test failed: {test_result['message']}")

        setattr(current_connection, "name", connection_update.name)
        setattr(current_connection, "api_key", connection_update.api_key)
        setattr(current_connection, "model", connection_update.model)
        setattr(current_connection, "configuration", connection_update.configuration)
        setattr(current_connection, "is_active", connection_update.is_active)

        return LLMConnectionResponse.model_validate(current_connection)

    async def delete_llm_connection(self, 
                                    current_user: UserResponse,
                                    connection_id: uuid.UUID) -> None:
        current_connection = await self._llm_repository.get_by_id(connection_id)
        if not current_connection:
            raise BusinessValidationError("LLM connection not found")
        self.__check_authorized(current_user, current_connection)
        await self._llm_repository.delete(current_connection)

    def test_llm_connection(self, test_config: LLMConnectionTest) -> dict:
        return self._tester.test_connection(
            provider=test_config.provider,
            api_key=test_config.api_key,
            model=test_config.model,
            configuration=test_config.configuration,
        )

    async def get_agent_definition(self, agent_id: uuid.UUID, current_user: UserResponse) -> Optional[AgentDefinitionResponse]:
        agent = await self._agent_definition_repository.get_by_id(agent_id)
        if not agent:
            return None

        connection = await self._get_llm_connection(agent.llm_connection_id)
        self.__check_authorized(current_user, connection)
        return AgentDefinitionResponse.model_validate(agent)
    
    async def create_agent_definition(
        self,
        agent_definition: AgentDefinitionCreate,
        current_user: UserResponse,
    ) -> AgentDefinitionResponse:
        connection = await self._get_llm_connection(agent_definition.llm_connection_id)
        self.__check_authorized(current_user, connection)

        new_agent = AgentDefinition(
            id=uuid.uuid4(),
            name=agent_definition.name,
            description=agent_definition.description,
            llm_connection_id=agent_definition.llm_connection_id,
            definition=agent_definition.definition,
            is_active=True,
        )

        self._agent_definition_repository.add(new_agent)
        return AgentDefinitionResponse.model_validate(new_agent)
    
    async def list_agent_definitions(self, current_user: UserResponse) -> List[AgentDefinitionResponse]:
        agents = await self._agent_definition_repository.get_all()
        visible: list[AgentDefinitionResponse] = []
        for agent in agents:
            try:
                connection = await self._get_llm_connection(agent.llm_connection_id)
                self.__check_authorized(current_user, connection)
                visible.append(AgentDefinitionResponse.model_validate(agent))
            except AuthorizationError:
                continue
        return visible
    
    async def update_agent_definition(
        self,
        current_user: UserResponse,
        agent_id: uuid.UUID,
        agent_update: AgentDefinitionUpdate,
    ) -> Optional[AgentDefinitionResponse]:
        current_agent: Optional[AgentDefinition] = await self._agent_definition_repository.get_by_id(agent_id)
        if not current_agent:
            return None

        connection_id = agent_update.llm_connection_id or current_agent.llm_connection_id
        connection = await self._get_llm_connection(connection_id)
        self.__check_authorized(current_user, connection)

        if agent_update.name is not None:
            current_agent.name = agent_update.name
        if agent_update.description is not None:
            current_agent.description = agent_update.description
        if agent_update.llm_connection_id is not None:
            current_agent.llm_connection_id = agent_update.llm_connection_id
        if agent_update.definition is not None:
            current_agent.definition = agent_update.definition
        if agent_update.is_active is not None:
            current_agent.is_active = agent_update.is_active

        return AgentDefinitionResponse.model_validate(current_agent)
    
    async def delete_agent_definition(self, current_user: UserResponse, agent_id: uuid.UUID) -> None:
        current_agent = await self._agent_definition_repository.get_by_id(agent_id)
        if not current_agent:
            raise BusinessValidationError("Agent definition not found")

        connection = await self._get_llm_connection(current_agent.llm_connection_id)
        self.__check_authorized(current_user, connection)
        await self._agent_definition_repository.delete(current_agent)
        
    def __check_authorized(
        self,
        current_user: Optional[UserResponse],
        connection: Optional[LLMConnection],
    ) -> None:
        if is_internal_service_call():
            return

        if current_user is None:
            raise BusinessValidationError("User must be authenticated to access LLM connections")

        if connection is None:
            raise BusinessValidationError("LLM connection not found")

        if not UserAuthorizedProvider.user_in_at_least_one_organization(current_user, [org.id for org in connection.organizations]):
            raise AuthorizationError("User does not have access to the specified LLM connection")

        if connection.projects:
            if not UserAuthorizedProvider.user_in_at_least_one_project(current_user, [proj.id for proj in connection.projects]):
                raise AuthorizationError("User does not have access to the specified LLM connection")

    async def _get_llm_connection(self, connection_id: uuid.UUID) -> LLMConnection:
        connection = await self._llm_repository.get_by_id(connection_id)
        if not connection:
            raise BusinessValidationError("LLM connection not found")
        return connection
