from dataclasses import dataclass, field
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Type
import uuid
from langbridge.packages.common.langbridge_common.contracts.jobs.agent_job import CreateAgentJobRequest
from langbridge.packages.common.langbridge_common.contracts.llm_connections import LLMConnectionSecretResponse
from langbridge.packages.common.langbridge_common.db.agent import AgentDefinition, LLMConnection
from langbridge.packages.common.langbridge_common.db.connector import Connector
from langbridge.packages.common.langbridge_common.db.job import JobEventRecord, JobRecord, JobStatus
from langbridge.packages.common.langbridge_common.db.semantic import SemanticModelEntry
from langbridge.packages.common.langbridge_common.repositories.agent_repository import AgentRepository
from langbridge.packages.common.langbridge_common.repositories.connector_repository import ConnectorRepository
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.common.langbridge_common.repositories.llm_connection_repository import LLMConnectionRepository
from langbridge.packages.common.langbridge_common.repositories.semantic_model_repository import SemanticModelRepository
from langbridge.packages.common.langbridge_common.utils.embedding_provider import EmbeddingProvider, EmbeddingProviderError
from langbridge.packages.connectors.langbridge_connectors.api.config import BaseConnectorConfigFactory, ConnectorRuntimeType, get_connector_config_factory
from langbridge.packages.connectors.langbridge_connectors.api.connector import ConnectorRuntimeTypeSqlDialectMap, ManagedVectorDB, SqlConnector, SqlDialetcs, VectorDBType
from langbridge.packages.connectors.langbridge_connectors.api.registry import SqlConnectorFactory, VectorDBConnectorFactory
from langbridge.packages.messaging.langbridge_messaging.contracts.base import MessageType
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.agent_job import AgentJobRequestMessage
from langbridge.packages.messaging.langbridge_messaging.handler import BaseMessageHandler
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.analyst.agent import AnalystAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.deep_research.agent import DeepResearchAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.planner.models import PlanningConstraints
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.planner.planner import PlanningAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.reasoning.agent import ReasoningAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.supervisor.orchestrator import SupervisorOrchestrator
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.visual.agent import VisualAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.web_search.agent import WebSearchAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.definitions.model import AgentDefinitionModel, DataAccessPolicy, ExecutionMode, ToolType
from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider.base import LLMProvider
from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider.factory import create_provider
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.semantic_search.tool import SemanticSearchTool
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.sql_analyst.tool import SqlAnalystTool
from langbridge.packages.semantic.langbridge_semantic.loader import load_semantic_model
from langbridge.packages.semantic.langbridge_semantic.model import SemanticModel


@dataclass(slots=True)
class _AgentToolConfig:
    allow_sql: bool
    allow_web_search: bool
    allow_deep_research: bool
    allow_visualization: bool
    sql_model_ids: set[uuid.UUID] = field(default_factory=set)
    web_search_defaults: dict[str, Any] = field(default_factory=dict)

class JobHandlerMessage(BaseMessageHandler):
    message_type: MessageType = MessageType.AGENT_JOB_REQUEST
    
    def __init__(self,
                job_repository: JobRepository,
                agent_definition_repository: AgentRepository,
                semantic_model_repository: SemanticModelRepository,
                llm_repository: LLMConnectionRepository,
                connector_repository: ConnectorRepository
                ):
        self._logger = logging.getLogger(__name__)
        self._job_repository = job_repository
        self._agent_definition_repository = agent_definition_repository
        self._semantic_model_repository = semantic_model_repository
        self._llm_repository = llm_repository
        self._connector_repository = connector_repository
        self._vector_factory = VectorDBConnectorFactory()
        self._sql_connector_factory = SqlConnectorFactory()
    
    async def handle(self, agent_job_request_payload: AgentJobRequestMessage) -> None:
        self._logger.info(f"Received agent job request with ID {agent_job_request_payload.job_id} and type {agent_job_request_payload.job_type}")

        job_record: JobRecord | None = await self._job_repository.get_by_id(agent_job_request_payload.job_id)

        if job_record is None:
            raise BusinessValidationError(f"Job with ID {agent_job_request_payload.job_id} does not exist.")
        
        job_record.status = JobStatus.running

        payload: CreateAgentJobRequest = CreateAgentJobRequest(**job_record.payload)
        
        agent_definition_record, agent_definition_model = await self._get_agent_definition(payload.agent_definition_id)

        llm_connection: LLMConnection = await self._get_llm_connection(
            getattr(agent_definition_record, "llm_connection_id")
        )

        llm_connection_response = LLMConnectionSecretResponse.model_validate(llm_connection)

        try:
            embedding_provider: EmbeddingProvider | None = EmbeddingProvider.from_llm_connection(llm_connection_response)
        except EmbeddingProviderError as exc:
            embedding_provider = None
            self._logger.warning(
                "request_id=%s embedding provider unavailable; skipping vector search: %s",
                job_record.id,
                exc,
            )

        tool_config: _AgentToolConfig = self._build_agent_tool_config(agent_definition_model)

        llm_provider: LLMProvider = create_provider(llm_connection)
        
        sql_analyst_tool, semantic_search_tools = await self._build_analyst_tools(tool_config, llm_provider, embedding_provider)

        supervisor_orchestrator = self._build_supervisor_orchestrator(tool_config, agent_definition_model, llm_provider, sql_analyst_tool, semantic_search_tools, embedding_provider)
        

        job_record.status = JobStatus.running

        job_record.job_events.append(JobEventRecord(event_type="AgentJobStarted", details={}))


        
    async def _get_agent_definition(self, agent_definition_id: uuid.UUID) -> Tuple[AgentDefinition, AgentDefinitionModel]:
        agent_definition = await self._agent_definition_repository.get_by_id(agent_definition_id)
        if agent_definition is None:
            raise BusinessValidationError(f"Agent definition with ID {agent_definition_id} does not exist.")

        return agent_definition, AgentDefinitionModel.model_validate(agent_definition.definition)
    
    async def _get_llm_connection(self, llm_connection_id: uuid.UUID) -> LLMConnection:
        llm_connection = await self._llm_repository.get_by_id(llm_connection_id)
        if llm_connection is None:
            raise BusinessValidationError(f"LLM connection with ID {llm_connection_id} does not exist.")

        return llm_connection

    async def _get_semantic_model_defintions(
        self, 
        semantic_model_ids: list[uuid.UUID]
    ) -> List[SemanticModelEntry]:
        return await self._semantic_model_repository.get_by_ids(semantic_model_ids)
    
    async def _get_connectors(self, connector_ids: set[uuid.UUID]) -> List[Connector]:
        return await self._connector_repository.get_by_ids(list(connector_ids))

    async def _build_analyst_tools(
            self,
            agent_tool_config: _AgentToolConfig,
            llm_provider: LLMProvider,
            embedding_provider: Optional[EmbeddingProvider]
    ) -> Tuple[List[SqlAnalystTool], List[SemanticSearchTool]]:
        
        if not agent_tool_config.allow_sql:
            return [], []

        semantic_model_entries: List[SemanticModelEntry] = await self._get_semantic_model_defintions(list(agent_tool_config.sql_model_ids))
        
        connector_ids = set()
        for entry in semantic_model_entries:
            connector_ids.add(entry.connector_id)

        connectors: List[Connector] = await self._get_connectors(connector_ids)
        
        connector_instances: Dict[uuid.UUID, SqlConnector] = {}
        sql_tools: List[SqlAnalystTool] = []
        semantic_search_tools: List[SemanticSearchTool] = []
        
        for entry in semantic_model_entries:
            connector: Connector | None = next((c for c in connectors if getattr(c, "id", None) == entry.connector_id), None)
            if connector is None:
                self._logger.warning(f"No connector found for semantic model {entry.id} (connector_id={entry.connector_id})")
                continue
            
            connector_id: uuid.UUID = getattr(connector, "id")
            connector_config_json = getattr(connector, "config_json")
            connector_type: ConnectorRuntimeType = ConnectorRuntimeType(connector.connector_type.upper())
            
            if connector_id not in connector_instances:
                dialect: SqlDialetcs | None = ConnectorRuntimeTypeSqlDialectMap.get(connector_type)
                if dialect is None:
                    raise BusinessValidationError(
                        f"Connector type {connector_type.value} does not support SQL operations."
                    )
                config_factory: Type[BaseConnectorConfigFactory] = get_connector_config_factory(
                    connector_type
                )
                connector_config: Dict[str, Any] = json.loads(connector_config_json)
                config_instance = config_factory.create(connector_config["config"])
                sql_connector: SqlConnector = self._sql_connector_factory.create_sql_connector(
                    dialect,
                    config_instance,
                    logger=self._logger,
                )
                connector_instances[connector_id] = sql_connector

            sql_connector: SqlConnector = connector_instances[connector_id]
            semantic_model: SemanticModel = load_semantic_model(entry.content_yaml)
            base_dialect = semantic_model.dialect
            dialect_str = str((base_dialect or getattr(sql_connector.DIALECT, "name", "postgres"))).lower()

            semantic_searches = await self._build_semantic_search_tools(
                llm_provider,
                semantic_model,
            )
            semantic_search_tools.extend(semantic_searches)

            tool = SqlAnalystTool(
                llm=llm_provider,
                semantic_model=semantic_model,
                connector=sql_connector,
                dialect=dialect_str,
                priority=0,
                embedder=embedding_provider,
            )

            sql_tools.append(tool)

        return sql_tools, semantic_search_tools
    
    def _get_vector_semantic_searches(self, semantic_model: SemanticModel) -> list[dict[str, Any]]:
        searches = []
        for table_key, table in semantic_model.tables.items():
            for dimension in table.dimensions or []:
                if not dimension.vectorized:
                    continue
                vector_index = dimension.vector_index or {}
                if not vector_index:
                    continue
                self._logger.info("Found vectorized dimension: %s.%s", table_key, dimension.name)
                vector_parameters = {
                    **vector_index,
                    "semantic_name": f"{semantic_model.name or 'semantic_model'}::{table_key}.{dimension.name}",
                }
                searches.append(
                    {
                        "metadata_filters": {},
                        "vector_parameters": vector_parameters,
                    }
                )
        return searches
    
    async def _build_semantic_search_tools(
        self,
        llm_provider: LLMProvider,
        semantic_model: SemanticModel,
    ) -> list[SemanticSearchTool]:
        tools: list[SemanticSearchTool] = []
        vector_searches = self._get_vector_semantic_searches(semantic_model)
        self._logger.info(
            "Building %d semantic search tools for model %s",
            len(vector_searches),
            semantic_model.name,
        )
        for vector_search in vector_searches:
            vector_params = vector_search.get("vector_parameters", {})
            if not vector_params:
                self._logger.warning(
                    "Skipping semantic search tool for model %s due to missing vector parameters in %s",
                    semantic_model.name, vector_search
                )
                continue
            self._logger.info(
                "Building semantic search tool for model %s with vector params %s",
                semantic_model.name,
                vector_params,
            )
            #TODO: Support other vector DB types (e.g., Pinecone, Weaviate) based on vector_params
            tool = await self._build_semantic_search_tool(
                llm_provider,
                vector_type=VectorDBType.FAISS,
                vector_params=vector_params,
            )
            tools.append(tool)
        return tools

    async def _build_semantic_search_tool(
        self,
        llm_provider: LLMProvider,
        vector_type: VectorDBType,
        vector_params: dict[str, Any],
    ) -> SemanticSearchTool:
        vector_managed_class_ref: Type[ManagedVectorDB] = (
            self._vector_factory.get_managed_vector_db_class_reference(vector_type)
        )
        #TODO: Support other vector DB types (e.g., Pinecone, Weaviate)
        vector_store: ManagedVectorDB = await vector_managed_class_ref.create_managed_instance(
            kwargs={
                "index_name": vector_params.get("vector_namespace")
            },
            logger=self._logger,
        )
        return SemanticSearchTool(
            semantic_name=vector_params.get("semantic_name", "default_search"),
            llm=llm_provider,
            embedding_model=vector_params.get("model"),
            vector_store=vector_store,
            entity_reconignition=True # trying out entity recognition
        )
    
    def _build_supervisor_orchestrator(
            self,
            tool_config: _AgentToolConfig,
            agent_definition: AgentDefinitionModel,
            llm_provider: LLMProvider,
            sql_tools: List[SqlAnalystTool],
            semantic_search_tools: List[SemanticSearchTool],
            _: Optional[EmbeddingProvider]
    ) -> SupervisorOrchestrator:
        
        planning_constraints = self._build_planning_constraints(tool_config, agent_definition)
        
        analyst_agent = self._build_analyst_agent(llm_provider, sql_tools, semantic_search_tools)
        visual_agent = self._build_visual_agent(llm_provider)
        planning_agent = self._build_planning_agent(llm_provider)
        reasoning_agent = self._build_reasoning_agent(llm_provider, planning_constraints)
        deep_research_agent = self._build_deep_research_agent(llm_provider)
        web_search_agent = self._build_web_search_agent(llm_provider)
        
        supervisor = SupervisorOrchestrator(
            analyst_agent=analyst_agent,
            visual_agent=visual_agent,
            planning_agent=planning_agent,
            reasoning_agent=reasoning_agent,
            deep_research_agent=deep_research_agent,
            web_search_agent=web_search_agent
        )
        return supervisor

    def _build_agent_tool_config(
        self,
        definition: AgentDefinitionModel,
    ) -> _AgentToolConfig:

        tools = list(definition.tools or [])
        
        sql_tools = [tool for tool in tools if tool.tool_type == ToolType.sql]
        allow_sql = len(sql_tools) > 0

        web_search_tools = [tool for tool in tools if tool.tool_type == ToolType.web]
        allow_web_search = len(web_search_tools) > 0

        allow_deep_research = AgentDefinitionModel.features.deep_research_enabled
        allow_visualization = AgentDefinitionModel.features.visualization_enabled

        sql_semantic_model_ids = [tool.get_sql_tool_config().definition_id for tool in sql_tools]

        return _AgentToolConfig(
            allow_sql=allow_sql,
            allow_web_search=allow_web_search,
            allow_deep_research=allow_deep_research,
            allow_visualization=allow_visualization,
            sql_model_ids=set(sql_semantic_model_ids),
        )
    
    def _build_planning_constraints(
        self,
        tool_config: _AgentToolConfig,
        agent_definition: AgentDefinitionModel
    ) -> PlanningConstraints:
        max_steps = agent_definition.execution.max_iterations
        ignore_max_steps = False
        if agent_definition.features.deep_research_enabled:
            ignore_max_steps = True

        prefer_low_latency = agent_definition.execution.mode == ExecutionMode.single_step
        max_steps = max(1, min(max_steps, 5)) if ExecutionMode.single_step else max_steps

        return PlanningConstraints(
            max_steps=agent_definition.execution.max_iterations,
            ignore_max_steps=ignore_max_steps,
            prefer_low_latency=prefer_low_latency,
            require_viz_when_chartable=agent_definition.features.visualization_enabled,
            allow_sql_analyst=tool_config.allow_sql,
            allow_web_search=tool_config.allow_web_search,
            allow_deep_research=tool_config.allow_deep_research
        )
    
    async def _build_planner_tool_context(
            self,
            agent_tool_config: _AgentToolConfig,
    ) -> Dict[str, Any]:
        semantic_model_entries: List[SemanticModelEntry] = await self._get_semantic_model_defintions(list(agent_tool_config.sql_model_ids))
        
        available_agents = [
            {
                "agent": "Analyst",
                "description": "Query structured data via semantic models (NL to SQL).",
                "enabled": agent_tool_config.allow_sql,
                "notes": "Uses the semantic_models list.",
            },
            {
                "agent": "Visual",
                "description": "Generate a visualization spec from analyst results.",
                "enabled": agent_tool_config.allow_visualization,
            },
            {
                "agent": "WebSearch",
                "description": "Search the web for sources and snippets.",
                "enabled": agent_tool_config.allow_web_search,
            },
            {
                "agent": "DocRetrieval",
                "description": "Synthesize insights from documents and sources.",
                "enabled": agent_tool_config.allow_deep_research,
            },
            {
                "agent": "Clarify",
                "description": "Ask a clarifying question when key details are missing.",
                "enabled": True,
            },
        ]

        semantic_model_tool_descriptions: Dict[str, str] = {}
        for entry in semantic_model_entries:
            semantic_model_tool_descriptions[str(entry.id)] = { # type: ignore
                'name': entry.name,
                'description': f"{entry.name} - {entry.description}",
                'yaml': f"yaml: {entry.content_yaml}",
            }

        return {
            "available_agents": available_agents,
            "semantic_models": semantic_model_tool_descriptions,
        }
    
    def _build_planning_agent(
            self,
            llm_provider: LLMProvider
    ) -> PlanningAgent:
        planning_agent = PlanningAgent(llm=llm_provider)
        return planning_agent
    
    def _build_reasoning_agent(
            self,
            llm_provider: LLMProvider,
            planning_constraints: PlanningConstraints
    ) -> ReasoningAgent:
        reasoning_agent = ReasoningAgent(llm=llm_provider, max_iterations=planning_constraints.max_steps)
        return reasoning_agent
    
    def _build_visual_agent(
            self,
            llm_provider: LLMProvider
    ) -> VisualAgent:
        visual_agent = VisualAgent(llm=llm_provider)
        return visual_agent
    
    def _build_deep_research_agent(
            self,
            llm_provider: LLMProvider
    ) -> DeepResearchAgent:
        deep_research_agent = DeepResearchAgent(llm=llm_provider)
        return deep_research_agent
    
    def _build_web_search_agent(
            self,
            llm_provider: LLMProvider
    ) -> WebSearchAgent:
        web_search_agent = WebSearchAgent(llm=llm_provider)
        return web_search_agent
    
    def _build_analyst_agent(
            self,
            llm_provider: LLMProvider,
            sql_tools: List[SqlAnalystTool],
            semantic_search_tools: List[SemanticSearchTool]
    ) -> AnalystAgent:
        analyst_agent = AnalystAgent(llm=llm_provider, sql_tools=sql_tools, search_tools=semantic_search_tools)
        return analyst_agent