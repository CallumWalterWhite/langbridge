
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional, Sequence, Type

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from langbridge.packages.connectors.langbridge_connectors.api.config import ConnectorRuntimeType
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.connectors.langbridge_connectors.api.registry import VectorDBConnectorFactory
from langbridge.packages.connectors.langbridge_connectors.api.connector import ManagedVectorDB, VectorDBType
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.analyst import AnalystAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.bi_copilot import BICopilotAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.deep_research import DeepResearchAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.planner import PlanningAgent, PlanningConstraints
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.visual import VisualAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.web_search import WebSearchAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.supervisor import SupervisorOrchestrator
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.supervisor.orchestrator import ReasoningAgent
from langbridge.packages.orchestrator.langbridge_orchestrator.definitions import (
    AgentDefinitionModel,
    DataAccessPolicy,
    ExecutionMode,
    GuardrailConfig,
    MemoryStrategy,
    OutputFormat,
    OutputSchema,
    PromptContract,
    ResponseMode,
)
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.semantic_query_builder import (
    QueryBuilderCopilotRequest,
    QueryBuilderCopilotResponse,
    SemanticQueryBuilderCopilotTool,
)
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.semantic_search import SemanticSearchTool
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.sql_analyst import SqlAnalystTool, load_semantic_model
from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider import (
    LLMProvider,
    create_provider
)
from langbridge.packages.orchestrator.langbridge_orchestrator.tools.sql_analyst.interfaces import SemanticModel
from langbridge.apps.api.langbridge_api.services.agent_service import AgentService
from langbridge.apps.api.langbridge_api.services.connector_service import ConnectorService
from langbridge.apps.api.langbridge_api.services.organization_service import OrganizationService
from langbridge.apps.api.langbridge_api.services.semantic import SemanticModelService, SemanticQueryService
from langbridge.packages.common.langbridge_common.utils.embedding_provider import EmbeddingProvider, EmbeddingProviderError

from langbridge.packages.common.langbridge_common.contracts.llm_connections import LLMConnectionSecretResponse
from langbridge.packages.common.langbridge_common.contracts.connectors import ConnectorResponse
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.threads import ThreadMessageResponse
from langbridge.apps.api.langbridge_api.db.threads import Role
from langbridge.apps.api.langbridge_api.services.thread_service import ThreadService


@dataclass(slots=True)
class _AgentToolConfig:
    allow_sql: bool = True
    allow_web_search: bool = True
    allow_deep_research: bool = True
    sql_model_ids: set[uuid.UUID] = field(default_factory=set)
    allowed_connector_ids: Optional[set[uuid.UUID]] = None
    denied_connector_ids: set[uuid.UUID] = field(default_factory=set)
    web_search_defaults: dict[str, Any] = field(default_factory=dict)


SQL_TOOL_NAMES = {"sql_analyst", "sql", "sql_analytics"}
WEB_TOOL_NAMES = {"web_search", "web_searcher", "web_search_agent"}
DOC_TOOL_NAMES = {"doc_retrieval", "deep_research", "research"}
MAX_CONTEXT_TURNS = 6


class OrchestratorService:
    def __init__(
        self,
        organization_service: OrganizationService,
        semantic_model_service: SemanticModelService,
        connector_service: ConnectorService,
        agent_service: AgentService,
        thread_service: ThreadService,
    ):
        self._organization_service = organization_service
        self._semantic_model_service = semantic_model_service
        self._connector_service = connector_service
        self._agent_service = agent_service
        self._thread_service = thread_service
        self._logger = logging.getLogger(__name__)
        self._vector_factory = VectorDBConnectorFactory()
        self._semantic_query_service = SemanticQueryService(
            semantic_model_service=semantic_model_service,
            connector_service=connector_service,
        )

    async def chat(
        self,
        msg: str,
        *,
        agent_id: uuid.UUID | None = None,
        thread_id: uuid.UUID | None = None,
        current_user: UserResponse | None = None,
    ) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        start_ts = time.perf_counter()
        self._logger.info("orchestrator.chat start request_id=%s", request_id)
        agent_definition: AgentDefinitionModel | None = None
        agent_record = None
        if agent_id is None:
            raise BusinessValidationError("Agent definition is required.")
        if current_user is None:
            raise BusinessValidationError("User must be authenticated to run an agent definition.")
        agent_record = await self._agent_service.get_agent_definition(agent_id, current_user)
        if not agent_record:
            raise BusinessValidationError("Agent definition not found.")
        agent_definition = (
            agent_record.definition
            if isinstance(agent_record.definition, AgentDefinitionModel)
            else AgentDefinitionModel.model_validate(agent_record.definition)
        )
        self._logger.debug(
            "request_id=%s using agent_definition id=%s name=%s",
            request_id,
            agent_record.id,
            agent_record.name
        )
        conversation_context = await self._load_conversation_context(
            thread_id=thread_id,
            current_user=current_user,
            agent_definition=agent_definition,
            request_id=request_id,
        )
        response_mode = agent_definition.execution.response_mode if agent_definition else ResponseMode.analyst
        self._logger.debug("request_id=%s response_mode=%s", request_id, response_mode.value)

        llm_connections = await self._agent_service.list_llm_connection_secrets()
        if not llm_connections:
            raise BusinessValidationError("No LLM connections configured")
        llm_connection = self._select_llm_connection(llm_connections, agent_record)
        self._logger.debug(
            "request_id=%s using llm_connection id=%s model=%s",
            request_id,
            llm_connection.id,
            llm_connection.model,
        )
        
        llm_provider: LLMProvider = create_provider(llm_connection)

        if response_mode == ResponseMode.chat:
            chat_response = await self._generate_chat_response(
                llm_provider,
                msg,
                conversation_context=conversation_context,
                request_id=request_id,
                prompt_contract=agent_definition.prompt if agent_definition else None,
                output_schema=agent_definition.output if agent_definition else None,
                guardrails=agent_definition.guardrails if agent_definition else None,
                response_mode=response_mode,
            )
            elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
            self._logger.info("orchestrator.chat complete request_id=%s elapsed_ms=%d", request_id, elapsed_ms)
            return {
                "result": None,
                "visualization": None,
                "summary": chat_response,
                "diagnostics": {
                    "response_mode": response_mode.value,
                    "total_elapsed_ms": elapsed_ms,
                },
            }

        try:
            embedding_provider: EmbeddingProvider | None = EmbeddingProvider.from_llm_connection(llm_connection)
        except EmbeddingProviderError as exc:
            embedding_provider = None
            self._logger.warning(
                "request_id=%s embedding provider unavailable; skipping vector search: %s",
                request_id,
                exc,
            )
        #TODO: revist this logic for the agent builder 
        tool_config = self._build_agent_tool_config(agent_definition)
        semantic_entries = await self._semantic_model_service.list_all_models()
        filtered_entries = (
            self._filter_semantic_entries(semantic_entries, tool_config)
            if tool_config.allow_sql
            else []
        )
        connectors: list[ConnectorResponse] = await self._connector_service.list_all_connectors()
        connector_lookup = {str(connector.id): connector for connector in connectors}
        self._logger.info(
            "request_id=%s loaded %d semantic entries, %d connectors",
            request_id,
            len(semantic_entries),
            len(connectors),
        )

        connector_instances: dict[str, Any] = {}
        tools: list[SqlAnalystTool] = []
        semantic_search_tools: list[SemanticSearchTool] = []

        if tool_config.allow_sql and not filtered_entries:
            self._logger.warning(
                "request_id=%s no semantic models matched agent tool constraints; disabling SQL analyst",
                request_id,
            )
            tool_config.allow_sql = False

        for entry in filtered_entries:
            connector_id = str(entry.connector_id)
            connector_entry = connector_lookup.get(connector_id)
            if not connector_entry:
                self._logger.warning(
                    "request_id=%s semantic model %s missing connector %s; skipping",
                    request_id,
                    entry.id,
                    connector_id,
                )
                continue

            connector_type = ConnectorRuntimeType(connector_entry.connector_type.upper())
            config = connector_entry.config or {}

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
            base_dialect = semantic_model.dialect

            semantic_searches = await self._build_semantic_search_tools(
                llm_provider,
                semantic_model,
            )
            semantic_search_tools.extend(semantic_searches)
                
            dialect = (base_dialect or getattr(sql_connector.DIALECT, "name", "postgres")).lower()
            self._logger.debug(
                "request_id=%s configured tool model=%s connector=%s dialect=%s",
                request_id,
                semantic_model.name or str(entry.id),
                connector_entry.name,
                dialect,
            )

            tool = SqlAnalystTool(
                llm=llm_provider,
                semantic_model=semantic_model,
                connector=sql_connector,
                dialect=dialect,
                priority=0,
                embedder=embedding_provider,
            )
            tools.append(tool)

        if tool_config.allow_sql and not tools:
            raise BusinessValidationError("No semantic models or connectors available for SQL analysis.")

        analyst_agent: AnalystAgent | None = (
            AnalystAgent(llm_provider, sql_tools=tools, search_tools=semantic_search_tools)
            if tools
            else None
        )
        visual_agent = VisualAgent(llm=llm_provider)
        planning_agent = PlanningAgent(llm=llm_provider, logger=self._logger)
        planning_constraints = self._build_planning_constraints(agent_definition, tool_config)
        reasoning_agent = self._build_reasoning_agent(agent_definition, llm_provider)
        deep_research_agent = DeepResearchAgent(llm=llm_provider, logger=self._logger)
        web_search_agent = WebSearchAgent(llm=llm_provider, logger=self._logger)
        planning_context: dict[str, Any] | None = dict(tool_config.web_search_defaults)
        planning_context.update(
            self._build_planner_tool_context(
                tool_config=tool_config,
                semantic_entries=filtered_entries,
                connector_lookup=connector_lookup,
            )
        )
        if conversation_context:
            planning_context["conversation_context"] = conversation_context
        if not planning_context:
            planning_context = None

        supervisor = SupervisorOrchestrator(
            analyst_agent=analyst_agent,
            visual_agent=visual_agent,
            planning_agent=planning_agent,
            reasoning_agent=reasoning_agent,
            deep_research_agent=deep_research_agent,
            web_search_agent=web_search_agent,
            bi_copilot_agent=self._build_bi_copilot_agent(llm_provider),
        )

        response = await supervisor.handle(
            user_query=msg,
            planning_constraints=planning_constraints,
            planning_context=planning_context,
        )
        diagnostics = response.get("diagnostics")
        if isinstance(diagnostics, dict):
            diagnostics["response_mode"] = response_mode.value
        summary = await self._summarize_response(
            llm_provider,
            msg,
            response,
            request_id=request_id,
            prompt_contract=agent_definition.prompt if agent_definition else None,
            output_schema=agent_definition.output if agent_definition else None,
            guardrails=agent_definition.guardrails if agent_definition else None,
            response_mode=response_mode,
        )
        response["summary"] = summary
        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        self._logger.info("orchestrator.chat complete request_id=%s elapsed_ms=%d", request_id, elapsed_ms)
        return response

    async def copilot(
        self,
        *,
        agent_id: uuid.UUID,
        copilot_request: QueryBuilderCopilotRequest,
        current_user: UserResponse | None,
    ) -> QueryBuilderCopilotResponse:
        """Expose the BI copilot tool for the query builder UI."""

        if current_user is None:
            raise BusinessValidationError("User must be authenticated to use the BI copilot.")

        agent_record = await self._agent_service.get_agent_definition(agent_id, current_user)
        if not agent_record:
            raise BusinessValidationError("Agent definition not found.")

        llm_connections = await self._agent_service.list_llm_connection_secrets()
        if not llm_connections:
            raise BusinessValidationError("No LLM connections configured")

        llm_connection = self._select_llm_connection(llm_connections, agent_record)
        llm_provider: LLMProvider = create_provider(llm_connection)

        supervisor = SupervisorOrchestrator(
            analyst_agent=None,
            visual_agent=VisualAgent(llm=llm_provider),
            planning_agent=None,
            reasoning_agent=None,
            deep_research_agent=None,
            web_search_agent=None,
            bi_copilot_agent=self._build_bi_copilot_agent(llm_provider),
        )

        return await supervisor.run_copilot(copilot_request)

    async def _load_conversation_context(
        self,
        *,
        thread_id: uuid.UUID | None,
        current_user: UserResponse | None,
        agent_definition: AgentDefinitionModel | None,
        request_id: str,
    ) -> str | None:
        if thread_id is None or current_user is None or agent_definition is None:
            return None
        if agent_definition.memory.strategy == MemoryStrategy.none:
            return None

        if agent_definition.memory.strategy not in (
            MemoryStrategy.conversation,
            MemoryStrategy.database,
            MemoryStrategy.transient,
        ):
            self._logger.info(
                "request_id=%s memory strategy '%s' not fully supported; using thread history fallback.",
                request_id,
                agent_definition.memory.strategy.value,
            )

        try:
            messages = await self._thread_service.list_messages_for_thread(thread_id, current_user)
        except Exception as exc:  # pragma: no cover - defensive guard
            self._logger.warning(
                "request_id=%s failed to load conversation history: %s",
                request_id,
                exc,
            )
            return None

        return self._render_conversation_context(messages, agent_definition.memory.ttl_seconds)

    async def _generate_chat_response(
        self,
        llm_provider: LLMProvider,
        question: str,
        *,
        conversation_context: str | None,
        request_id: str | None = None,
        prompt_contract: PromptContract | None = None,
        output_schema: OutputSchema | None = None,
        guardrails: GuardrailConfig | None = None,
        response_mode: ResponseMode | None = None,
    ) -> str:
        prompt_sections: list[str] = []
        if conversation_context:
            prompt_sections.append(f"Conversation so far:\n{conversation_context}")
        prompt_sections.append(f"User: {question.strip()}")
        if output_schema:
            prompt_sections.append(f"Output format: {output_schema.format.value}.")
            if output_schema.format == OutputFormat.json and output_schema.json_schema:
                schema_text = json.dumps(output_schema.json_schema, indent=2, sort_keys=True)
                prompt_sections.append(f"JSON schema:\n{schema_text}")
            if output_schema.format == OutputFormat.markdown and output_schema.markdown_template:
                prompt_sections.append(f"Markdown template:\n{output_schema.markdown_template}")
        prompt_sections.append("Assistant:")

        messages: list[BaseMessage] = []
        system_sections: list[str] = []
        mode_prompt = self._chat_mode_prompt(response_mode)
        if mode_prompt:
            system_sections.append(mode_prompt)
        if prompt_contract:
            for section in (
                prompt_contract.system_prompt,
                prompt_contract.user_instructions,
                prompt_contract.style_guidance,
            ):
                if section:
                    system_sections.append(section.strip())
        if system_sections:
            messages.append(SystemMessage(content="\n\n".join(system_sections)))
        messages.append(HumanMessage(content="\n\n".join(prompt_sections)))

        try:
            llm_response = await llm_provider.ainvoke(messages, temperature=0.4, max_tokens=900)
        except Exception as exc:  # pragma: no cover - defensive guard against transient LLM failures
            suffix = f" request_id={request_id}" if request_id else ""
            self._logger.warning("Failed to generate chat response%s: %s", suffix, exc, exc_info=True)
            return "Response unavailable due to temporary AI service issues."

        if isinstance(llm_response, BaseMessage):
            response_text = str(llm_response.content).strip()
        else:
            response_text = str(llm_response).strip()

        if not response_text:
            return "No response produced."
        return self._enforce_guardrails(response_text, guardrails)

    @staticmethod
    def _render_conversation_context(
        messages: Sequence[ThreadMessageResponse],
        ttl_seconds: int | None,
    ) -> str | None:
        if not messages:
            return None

        filtered = OrchestratorService._filter_messages_by_ttl(messages, ttl_seconds)
        if not filtered:
            return None

        assistant_by_parent: dict[uuid.UUID, ThreadMessageResponse] = {}
        for message in filtered:
            if message.role == Role.assistant and message.parent_message_id:
                assistant_by_parent[message.parent_message_id] = message

        turns: list[str] = []
        for message in filtered:
            if message.role != Role.user:
                continue
            user_text = OrchestratorService._read_text_field(message.content, "text")
            if not user_text:
                continue
            assistant = assistant_by_parent.get(message.id)
            assistant_text = OrchestratorService._read_text_field(
                assistant.content if assistant else None,
                "summary",
            )
            if not assistant_text and assistant and assistant.error:
                assistant_text = OrchestratorService._read_text_field(assistant.error, "message")
                if not assistant_text:
                    assistant_text = str(assistant.error)

            if assistant_text:
                turns.append(f"User: {user_text}\nAssistant: {assistant_text}")
            else:
                turns.append(f"User: {user_text}")

        if not turns:
            return None
        return "\n\n".join(turns[-MAX_CONTEXT_TURNS:])

    @staticmethod
    def _filter_messages_by_ttl(
        messages: Sequence[ThreadMessageResponse],
        ttl_seconds: int | None,
    ) -> list[ThreadMessageResponse]:
        if not ttl_seconds:
            return list(messages)

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=int(ttl_seconds))
        filtered: list[ThreadMessageResponse] = []
        for message in messages:
            created_at = OrchestratorService._normalize_timestamp(message.created_at)
            if created_at and created_at >= cutoff:
                filtered.append(message)
        return filtered

    @staticmethod
    def _normalize_timestamp(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _read_text_field(payload: Any, key: str) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return None
    
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
    

    async def _summarize_response(
        self,
        llm_provider: LLMProvider,
        question: str,
        response_payload: dict[str, Any],
        *,
        request_id: str | None = None,
        prompt_contract: PromptContract | None = None,
        output_schema: OutputSchema | None = None,
        guardrails: GuardrailConfig | None = None,
        response_mode: ResponseMode | None = None,
    ) -> str:
        """
        Generate a concise natural language summary of the orchestrated response.
        """

        summary_intro, summary_tail = self._summary_prompt_parts(response_mode)
        preview = self._render_tabular_preview(response_payload.get("result"))
        viz_summary = self._summarise_visualization(response_payload.get("visualization"))

        prompt_sections = [
            summary_intro,
            f"Original question:\n{question.strip()}",
            f"Tabular result preview:\n{preview}",
        ]
        if viz_summary:
            prompt_sections.append(f"Visualization guidance:\n{viz_summary}")
        if output_schema:
            prompt_sections.append(f"Output format: {output_schema.format.value}.")
            if output_schema.format == OutputFormat.json and output_schema.json_schema:
                schema_text = json.dumps(output_schema.json_schema, indent=2, sort_keys=True)
                prompt_sections.append(f"JSON schema:\n{schema_text}")
            if output_schema.format == OutputFormat.markdown and output_schema.markdown_template:
                prompt_sections.append(f"Markdown template:\n{output_schema.markdown_template}")
        if summary_tail:
            prompt_sections.append(summary_tail)

        prompt = "\n\n".join(prompt_sections)

        messages: list[BaseMessage] = []
        if prompt_contract:
            system_sections = [
                section.strip()
                for section in [
                    prompt_contract.system_prompt,
                    prompt_contract.user_instructions,
                    prompt_contract.style_guidance,
                ]
                if section
            ]
            if system_sections:
                messages.append(SystemMessage(content="\n\n".join(system_sections)))
        messages.append(HumanMessage(content=prompt))

        try:
            llm_response = await llm_provider.ainvoke(messages)
        except Exception as exc:  # pragma: no cover - defensive guard against transient LLM failures
            suffix = f" request_id={request_id}" if request_id else ""
            self._logger.warning("Failed to generate summary%s: %s", suffix, exc, exc_info=True)
            return "Summary unavailable due to temporary AI service issues."

        if isinstance(llm_response, BaseMessage):
            summary_text = str(llm_response.content).strip()
        else:
            summary_text = str(llm_response).strip()

        if not summary_text:
            return "No summary produced."
        return self._enforce_guardrails(summary_text, guardrails)

    @staticmethod
    def _summarise_visualization(visualization: Any) -> str:
        if not isinstance(visualization, dict) or not visualization:
            return ""

        parts: list[str] = []
        chart_type = visualization.get("chart_type")
        if chart_type:
            parts.append(f"type={chart_type}")
        x_axis = visualization.get("x")
        if x_axis:
            parts.append(f"x={x_axis}")
        y_axis = visualization.get("y")
        if isinstance(y_axis, (list, tuple)):
            if y_axis:
                parts.append(f"y={', '.join(map(str, y_axis))}")
        elif y_axis:
            parts.append(f"y={y_axis}")
        group_by = visualization.get("group_by")
        if group_by:
            parts.append(f"group_by={group_by}")
        return ", ".join(parts)

    @staticmethod
    def _render_tabular_preview(result: Any, *, max_rows: int = 8) -> str:
        if not isinstance(result, dict) or not result:
            return "No tabular result was returned."

        columns = result.get("columns") or []
        rows = result.get("rows") or []
        if not columns:
            return "Result did not include column metadata."
        if not rows:
            return "No rows matched the query."

        header = " | ".join(str(column) for column in columns)
        separator = "-+-".join("-" * max(len(str(column)), 3) for column in columns)

        preview_lines: list[str] = []
        for index, raw_row in enumerate(rows[:max_rows]):
            row_values = OrchestratorService._coerce_row_values(columns, raw_row)
            formatted = " | ".join(OrchestratorService._format_cell(value) for value in row_values)
            preview_lines.append(formatted)

        if len(rows) > max_rows:
            preview_lines.append(f"... ({len(rows) - max_rows} additional rows truncated)")

        return "\n".join([header, separator, *preview_lines])

    @staticmethod
    def _coerce_row_values(columns: list[str], row: Any) -> list[Any]:
        if isinstance(row, dict):
            return [row.get(column) for column in columns]
        if isinstance(row, (list, tuple)):
            values = list(row)
            if len(values) >= len(columns):
                return values[: len(columns)]
            values.extend([None] * (len(columns) - len(values)))
            return values
        return [row] + [None] * (len(columns) - 1)

    @staticmethod
    def _format_cell(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, float):
            formatted = f"{value:.4f}".rstrip("0").rstrip(".")
            return formatted or "0"
        return str(value)

    def _select_llm_connection(
        self,
        llm_connections: list[LLMConnectionSecretResponse],
        agent_record: Any | None,
    ) -> LLMConnectionSecretResponse:
        if agent_record is None:
            return llm_connections[0]

        desired_id = getattr(agent_record, "llm_connection_id", None)
        for connection in llm_connections:
            if connection.id == desired_id:
                return connection

        raise BusinessValidationError("LLM connection for the selected agent definition was not found.")

    def _build_bi_copilot_agent(self, llm_provider: LLMProvider) -> BICopilotAgent:
        tool = SemanticQueryBuilderCopilotTool(
            llm=llm_provider,
            semantic_query_service=self._semantic_query_service,
            logger=self._logger,
        )
        return BICopilotAgent(tool=tool, logger=self._logger)

    def _build_agent_tool_config(
        self,
        definition: AgentDefinitionModel | None,
    ) -> _AgentToolConfig:
        config = _AgentToolConfig()
        if not definition:
            return config

        tools = list(definition.tools or [])
        access_policy = definition.access_policy or DataAccessPolicy()
        allowed_connectors = set(access_policy.allowed_connectors or [])
        denied_connectors = set(access_policy.denied_connectors or [])
        config.denied_connector_ids = denied_connectors

        if not tools:
            config.allowed_connector_ids = allowed_connectors or None
            return config

        normalized_names = {self._normalize_tool_name(tool.name) for tool in tools}
        config.allow_sql = any(name in SQL_TOOL_NAMES for name in normalized_names)
        config.allow_web_search = any(name in WEB_TOOL_NAMES for name in normalized_names)
        config.allow_deep_research = any(name in DOC_TOOL_NAMES for name in normalized_names)

        sql_connector_ids: set[uuid.UUID] = set()
        for tool in tools:
            tool_name = self._normalize_tool_name(tool.name)
            if tool_name not in SQL_TOOL_NAMES:
                continue
            if tool.connector_id:
                sql_connector_ids.add(tool.connector_id)
            definition_id = self._coerce_uuid(tool.config.get("definition_id")) if isinstance(tool.config, dict) else None
            if definition_id:
                config.sql_model_ids.add(definition_id)

        if sql_connector_ids:
            config.allowed_connector_ids = (
                sql_connector_ids.intersection(allowed_connectors)
                if allowed_connectors
                else sql_connector_ids
            )
        else:
            config.allowed_connector_ids = allowed_connectors or None

        for tool in tools:
            tool_name = self._normalize_tool_name(tool.name)
            if tool_name not in WEB_TOOL_NAMES:
                continue
            if isinstance(tool.config, dict):
                for key in ("region", "safe_search", "max_results"):
                    if key in tool.config and tool.config[key] not in (None, ""):
                        config.web_search_defaults[key] = tool.config[key]

        return config

    def _filter_semantic_entries(
        self,
        entries: Iterable[Any],
        tool_config: _AgentToolConfig,
    ) -> list[Any]:
        filtered: list[Any] = []
        for entry in entries:
            if tool_config.sql_model_ids and entry.id not in tool_config.sql_model_ids:
                continue
            if (
                tool_config.allowed_connector_ids is not None
                and entry.connector_id not in tool_config.allowed_connector_ids
            ):
                continue
            if tool_config.denied_connector_ids and entry.connector_id in tool_config.denied_connector_ids:
                continue
            filtered.append(entry)
        return filtered

    def _build_planning_constraints(
        self,
        definition: AgentDefinitionModel | None,
        tool_config: _AgentToolConfig,
    ) -> PlanningConstraints | None:
        if not definition:
            return None

        max_steps = max(1, min(int(definition.execution.max_steps_per_iteration), 10))
        prefer_low_latency = definition.execution.mode == ExecutionMode.single_step

        return PlanningConstraints(
            max_steps=max_steps,
            prefer_low_latency=prefer_low_latency,
            allow_sql_analyst=tool_config.allow_sql,
            allow_web_search=tool_config.allow_web_search,
            allow_deep_research=tool_config.allow_deep_research,
        )

    @staticmethod
    def _build_planner_tool_context(
        *,
        tool_config: _AgentToolConfig,
        semantic_entries: Sequence[Any],
        connector_lookup: dict[str, ConnectorResponse],
        max_models: int = 25,
    ) -> dict[str, Any]:
        available_agents = [
            {
                "agent": "Analyst",
                "description": "Query structured data via semantic models (NL to SQL).",
                "enabled": tool_config.allow_sql,
                "notes": "Uses the semantic_models list.",
            },
            {
                "agent": "Visual",
                "description": "Generate a visualization spec from analyst results.",
                "enabled": tool_config.allow_sql,
            },
            {
                "agent": "WebSearch",
                "description": "Search the web for sources and snippets.",
                "enabled": tool_config.allow_web_search,
            },
            {
                "agent": "DocRetrieval",
                "description": "Synthesize insights from documents and sources.",
                "enabled": tool_config.allow_deep_research,
            },
            {
                "agent": "Clarify",
                "description": "Ask a clarifying question when key details are missing.",
                "enabled": True,
            },
        ]

        semantic_models: list[dict[str, Any]] = []
        for entry in list(semantic_entries)[:max_models]:
            connector_id = str(getattr(entry, "connector_id", "") or "")
            connector = connector_lookup.get(connector_id)
            description = (getattr(entry, "description", "") or "").strip()
            if len(description) > 180:
                description = f"{description[:177]}..."
            semantic_models.append(
                {
                    "id": str(getattr(entry, "id", "") or ""),
                    "name": getattr(entry, "name", "") or "",
                    "description": description or None,
                    "connector": connector.name if connector else None,
                    "connector_type": getattr(connector, "connector_type", None) if connector else None,
                }
            )

        return {
            "available_agents": available_agents,
            "semantic_models": semantic_models,
            "semantic_models_count": len(semantic_entries),
            "semantic_models_truncated": len(semantic_entries) > max_models,
        }

    def _build_reasoning_agent(
        self,
        definition: AgentDefinitionModel | None,
        llm_client: LLMProvider,
    ) -> ReasoningAgent | None:
        if not definition:
            return None
        max_iterations = max(1, int(definition.execution.max_iterations))
        if definition.execution.mode == ExecutionMode.single_step:
            max_iterations = 1
        return ReasoningAgent(max_iterations=max_iterations, logger=self._logger, llm=llm_client)

    @staticmethod
    def _normalize_tool_name(name: str) -> str:
        return str(name or "").strip().lower()

    @staticmethod
    def _coerce_uuid(value: Any) -> uuid.UUID | None:
        if isinstance(value, uuid.UUID):
            return value
        if isinstance(value, str):
            try:
                return uuid.UUID(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _chat_mode_prompt(response_mode: ResponseMode | None) -> str | None:
        if response_mode == ResponseMode.chat:
            return (
                "You are a helpful conversational assistant. Answer directly, keep a friendly tone, "
                "and ask a concise clarifying question when needed."
            )
        if response_mode == ResponseMode.executive:
            return "You are an executive briefing assistant. Keep responses concise and decision-focused."
        if response_mode == ResponseMode.explainer:
            return "You are a plain-language explainer. Use simple terms and avoid jargon."
        return None

    @staticmethod
    def _summary_prompt_parts(response_mode: ResponseMode | None) -> tuple[str, str]:
        mode = response_mode or ResponseMode.analyst
        if mode == ResponseMode.chat:
            mode = ResponseMode.analyst
        if mode == ResponseMode.executive:
            return (
                "You are an executive briefing assistant. Summarize the findings for a leadership audience.",
                "Return 3 bullet points and 1 recommended action. Mention if the dataset is empty.",
            )
        if mode == ResponseMode.explainer:
            return (
                "You are a data explainer. Summarize for a non-technical audience in 3-5 sentences.",
                "Avoid jargon, define any terms, and mention if the dataset is empty.",
            )
        return (
            "You are a senior analytics assistant. Summarize the findings for a business stakeholder in 2-3 sentences.",
            "Highlight the most important metric, call out notable changes or trends, and mention if the dataset is empty.",
        )

    @staticmethod
    def _enforce_guardrails(
        summary: str,
        guardrails: GuardrailConfig | None,
    ) -> str:
        if not guardrails or not guardrails.moderation_enabled:
            return summary
        if not guardrails.regex_denylist:
            return summary

        for pattern in guardrails.regex_denylist:
            try:
                if re.search(pattern, summary):
                    return guardrails.escalation_message or "Response blocked by content guardrails."
            except re.error:
                continue
        return summary
