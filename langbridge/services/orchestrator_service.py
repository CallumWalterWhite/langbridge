from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from connectors.config import ConnectorRuntimeType
from errors.application_errors import BusinessValidationError
from orchestrator.agents.analyst import AnalystAgent
from orchestrator.agents.visual import VisualAgent
from orchestrator.agents.supervisor import SupervisorOrchestrator
from orchestrator.tools.sql_analyst import SqlAnalystTool, load_semantic_model
from orchestrator.tools.sql_analyst.interfaces import LLMClient
from services.agent_service import AgentService
from services.connector_service import ConnectorService
from services.organization_service import OrganizationService
from services.semantic_model_service import SemanticModelService

from db.agent import LLMConnection


class _ChatModelLLMClient(LLMClient):
    """
    Adapter that exposes a LangChain chat model via the lightweight LLMClient protocol.
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._chat_model = chat_model

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        # The LangChain ChatOpenAI model handles temperature/max tokens during instantiation.
        # We keep the parameters for protocol compatibility.
        response = self._chat_model.invoke(prompt)
        if isinstance(response, BaseMessage):
            return str(response.content)
        return str(response)


class OrchestratorService:
    def __init__(
        self,
        organization_service: OrganizationService,
        semantic_model_service: SemanticModelService,
        connector_service: ConnectorService,
        agent_service: AgentService,
    ):
        self._organization_service = organization_service
        self._semantic_model_service = semantic_model_service
        self._connector_service = connector_service
        self._agent_service = agent_service

    async def chat(self, msg: str) -> dict[str, Any]:
        llm_connections = await self._agent_service.list_llm_connections()
        if not llm_connections:
            raise BusinessValidationError("No LLM connections configured")
        llm_connection: LLMConnection = llm_connections[0]
        base_llm: BaseChatModel = ChatOpenAI(
            model=llm_connection.model,
            temperature=0.1,
            api_key=llm_connection.api_key,
        )
        llm_client = _ChatModelLLMClient(base_llm)

        semantic_entries = await self._semantic_model_service.list_all_models()
        connectors = await self._connector_service.list_all_connectors()
        connector_lookup = {str(connector.id): connector for connector in connectors}

        connector_instances: dict[str, Any] = {}
        tools: list[SqlAnalystTool] = []

        for entry in semantic_entries:
            connector_id = str(entry.connector_id)
            connector_entry = connector_lookup.get(connector_id)
            if not connector_entry:
                continue

            connector_type = ConnectorRuntimeType(connector_entry.connector_type.upper())
            config = json.loads(connector_entry.config_json)

            if connector_id not in connector_instances:
                connector_instances[connector_id] = await self._connector_service.async_create_sql_connector(
                    connector_type,
                    config,
                )

            sql_connector = connector_instances[connector_id]
            semantic_model = load_semantic_model(entry.content_yaml)
            if not semantic_model.name:
                semantic_model.name = entry.name or f"model_{entry.id}"
            if not semantic_model.connector:
                semantic_model.connector = connector_entry.name
            dialect = (semantic_model.dialect or getattr(sql_connector.DIALECT, "name", "postgres")).lower()

            tool = SqlAnalystTool(
                llm=llm_client,
                semantic_model=semantic_model,
                connector=sql_connector,
                dialect=dialect,
            )
            tools.append(tool)

        if not tools:
            raise BusinessValidationError("No semantic models or connectors available for SQL analysis.")

        analyst_agent = AnalystAgent(tools)
        visual_agent = VisualAgent()

        supervisor = SupervisorOrchestrator(
            analyst_agent=analyst_agent,
            visual_agent=visual_agent,
        )

        return await supervisor.handle(user_query=msg)
