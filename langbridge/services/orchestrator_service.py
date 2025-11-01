import asyncio
import json

from connectors.config import ConnectorRuntimeType

from services.agent_service import AgentService
from services.connector_service import ConnectorService
from services.semantic_model_service import SemanticModelService
from services.organization_service import OrganizationService

from db.agent import LLMConnection

from orchestrator.agents.analyst_agent import AnalystAgent
from orchestrator.agents.visual_agent import VisualAgent
from orchestrator.agents.supervisor_orchestrator import (
    OrchestrationContext,
    SupervisorOrchestrator,
)

from connectors.registry import ConnectorInstanceRegistry

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from errors.application_errors import BusinessValidationError

class OrchestratorService:
    def __init__(
            self,
            organization_service: OrganizationService,
            semantic_model_service: SemanticModelService,
            connector_service: ConnectorService,
            agent_service: AgentService):
        self._organization_service = organization_service
        self._semantic_model_service = semantic_model_service
        self._connector_service = connector_service
        self._agent_service = agent_service
        self._semantic_model_builder = semantic_model_service._builder
        
        
    async def chat(
        self,
        msg: str,
    ):
        llm_connections = await self._agent_service.list_llm_connections()
        if not llm_connections:
            raise BusinessValidationError("No LLM connections configured")
        llm_connection: LLMConnection = llm_connections[0]  # For simplicity, pick the first connection
        llm: BaseChatModel = ChatOpenAI(
            model=llm_connection.model,
            temperature=0.2, # set from llm connection?
            api_key=llm_connection.api_key,
        )
        
        
        semantic_models = await self._semantic_model_service.list_all_models()
        
        available_semantic_models = []
        
        for model in semantic_models:
            available_semantic_models.append(self._semantic_model_builder.parse_yaml_to_model(model.content_yaml))
        
        available_connectors = await self._connector_service.list_all_connectors()
        
        connector_registry = ConnectorInstanceRegistry()
        
        for connector in available_connectors:
            sql_connector = await self._connector_service.async_create_sql_connector(
                ConnectorRuntimeType.SQLITE,
                (json.loads(connector.config_json))
            )
            connector_registry.add(sql_connector, 'Sqlite')
        
        analyst_agent = AnalystAgent(
            llm=llm,
            registry=connector_registry,
            summarizer=llm
        )
        
        visual_agent = VisualAgent()    
        
        supervisor = SupervisorOrchestrator(
            analyst_agent=analyst_agent,
            visual_agent=visual_agent,
        )
        
        context = OrchestrationContext(
            workspace_id=None,
            available_semantic_models=available_semantic_models,
            available_connectors=available_connectors,
        )
        result = await asyncio.create_task(
            supervisor.handle(
            user_query=msg,
            context=context,
            )
        )
        return result
        
        
        
