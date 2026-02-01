from dataclasses import dataclass, field
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Type
import uuid
from langbridge.packages.common.langbridge_common.contracts.jobs.agent_job import CreateAgentJobRequest
from langbridge.packages.common.langbridge_common.contracts.llm_connections import LLMProvider
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
from langbridge.packages.connectors.langbridge_connectors.api.config import BaseConnectorConfigFactory, ConnectorRuntimeType, get_connector_config_factory
from langbridge.packages.connectors.langbridge_connectors.api.connector import ConnectorRuntimeTypeSqlDialectMap, SqlConnector, SqlDialetcs
from langbridge.packages.connectors.langbridge_connectors.api.registry import SqlConnectorFactory, VectorDBConnectorFactory
from langbridge.packages.messaging.langbridge_messaging.contracts.base import MessageType
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.agent_job import AgentJobRequestMessage
from langbridge.packages.messaging.langbridge_messaging.handler import BaseMessageHandler
from langbridge.packages.orchestrator.langbridge_orchestrator.definitions.model import AgentDefinitionModel, DataAccessPolicy, ToolType
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

        job_record.job_events.append(JobEventRecord(event_type="AgentJobStarted", details={}))

        await self._job_repository.update(job_record)
        
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

    async def _build_sql_analyst_tools(
            self,
            agent_tool_config: _AgentToolConfig,
            llm_provider: LLMProvider
    ) -> List[SqlAnalystTool]:
        if not agent_tool_config.allow_sql:
            return []

        semantic_model_entries: List[SemanticModelEntry] = await self._get_semantic_model_defintions(list(agent_tool_config.sql_model_ids))
        
        connector_ids = set()
        for entry in semantic_model_entries:
            connector_ids.add(entry.connector_id)

        connectors: List[Connector] = await self._get_connectors(connector_ids)
        
        connector_instances: Dict[uuid.UUID, SqlConnector] = {}
        sql_tools: List[SqlAnalystTool] = []
        
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
            dialect = (base_dialect or getattr(sql_connector.DIALECT, "name", "postgres")).lower()

            tool = SqlAnalystTool(
                llm=llm_provider,
                semantic_model=semantic_model,
                connector=sql_connector,
                dialect=dialect,
                priority=0,
                # embedder=embedding_provider,
            )

            sql_tools.append(tool)

        return sql_tools
        



    

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