import uuid
from typing import List, Optional

from db.agent import LLMConnection
from errors.application_errors import BusinessValidationError
from models.llm_connections import (
    LLMConnectionCreate,
    LLMConnectionResponse,
    LLMConnectionSecretResponse,
    LLMConnectionTest,
    LLMConnectionUpdate,
    LLMProvider,
)
from repositories.llm_connection_repository import LLMConnectionRepository
from utils.llm.llm_tester import LLMConnectionTester


class AgentService:
    def __init__(self, repository: LLMConnectionRepository) -> None:
        self._repository = repository
        self._tester = LLMConnectionTester()

    async def create_llm_connection(
        self,
        connection: LLMConnectionCreate,
    ) -> LLMConnectionResponse:
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

        self._repository.add(new_connection)
        return LLMConnectionResponse.model_validate(new_connection)

    async def list_llm_connections(self) -> List[LLMConnectionResponse]:
        connections = await self._repository.get_all()
        return [LLMConnectionResponse.model_validate(conn) for conn in connections]

    async def list_llm_connection_secrets(self) -> List[LLMConnectionSecretResponse]:
        connections = await self._repository.get_all()
        return [LLMConnectionSecretResponse.model_validate(conn) for conn in connections]

    async def get_llm_connection(self, connection_id: uuid.UUID) -> Optional[LLMConnectionResponse]:
        connection = await self._repository.get_by_id(connection_id)
        if not connection:
            return None
        return LLMConnectionResponse.model_validate(connection)

    async def update_llm_connection(
        self,
        connection_id: uuid.UUID,
        connection_update: LLMConnectionUpdate,
    ) -> Optional[LLMConnectionResponse]:
        current_connection: Optional[LLMConnection] = await self._repository.get_by_id(connection_id)
        if not current_connection:
            return None

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

    async def delete_llm_connection(self, connection_id: uuid.UUID) -> None:
        current_connection = await self._repository.get_by_id(connection_id)
        if not current_connection:
            raise BusinessValidationError("LLM connection not found")
        await self._repository.delete(current_connection)

    def test_llm_connection(self, test_config: LLMConnectionTest) -> dict:
        return self._tester.test_connection(
            provider=test_config.provider,
            api_key=test_config.api_key,
            model=test_config.model,
            configuration=test_config.configuration,
        )
