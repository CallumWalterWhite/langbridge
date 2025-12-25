
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from connectors.config import ConnectorRuntimeType
from errors.application_errors import BusinessValidationError
from orchestrator.agents.analyst import AnalystAgent
from orchestrator.agents.planner import PlanningConstraints
from orchestrator.agents.visual import VisualAgent
from orchestrator.agents.supervisor import SupervisorOrchestrator
from orchestrator.agents.supervisor.orchestrator import ReasoningAgent
from orchestrator.definitions import (
    AgentDefinitionModel,
    DataAccessPolicy,
    ExecutionMode,
    GuardrailConfig,
    MemoryStrategy,
    OutputFormat,
    OutputSchema,
    PromptContract,
)
from orchestrator.tools.sql_analyst import SqlAnalystTool, load_semantic_model
from orchestrator.tools.sql_analyst.interfaces import (
    AnalystQueryResponse,
    LLMClient,
    SemanticModel,
    UnifiedSemanticModel,
)
from services.agent_service import AgentService
from services.connector_service import ConnectorService
from services.organization_service import OrganizationService
from services.semantic_model_service import SemanticModelService
from utils.embedding_provider import EmbeddingProvider, EmbeddingProviderError

from models.llm_connections import LLMConnectionSecretResponse
from models.connectors import ConnectorResponse
from models.auth import UserResponse
from models.threads import ThreadMessageResponse
from db.threads import Role
from services.thread_service import ThreadService


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


class _DisabledAnalystAgent:
    def __init__(self, *, reason: str) -> None:
        self._reason = reason

    async def answer_async(
        self,
        question: str,
        *,
        conversation_context: str | None = None,
        filters: dict | None = None,
        limit: int | None = None,
    ) -> AnalystQueryResponse:
        return AnalystQueryResponse(
            sql_canonical="",
            sql_executable="",
            dialect="n/a",
            model_name="",
            result=None,
            error=self._reason,
            execution_time_ms=None,
        )


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
        
        
        llm_conn_config = llm_connection.configuration or {}
        llm_conn_temperature = 0.2 # default temperature
        if llm_conn_config.get("temperature") is not None:
            self._logger.debug(
                "request_id=%s overriding llm temperature to %s from connection config",
                request_id,
                llm_conn_config.get("temperature"),
            )
            try:
                llm_conn_temperature = float(llm_conn_config.get("temperature"))
            except (ValueError, TypeError):
                pass
        
        base_llm: BaseChatModel = ChatOpenAI(
            model=llm_connection.model,
            temperature=llm_conn_temperature,
            api_key=llm_connection.api_key,
        )
        llm_client = _ChatModelLLMClient(base_llm)
        try:
            embedding_provider: EmbeddingProvider | None = EmbeddingProvider.from_llm_connection(llm_connection)
        except EmbeddingProviderError as exc:
            embedding_provider = None
            self._logger.warning(
                "request_id=%s embedding provider unavailable; skipping vector search: %s",
                request_id,
                exc,
            )

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
            base_dialect = None
            if isinstance(semantic_model, UnifiedSemanticModel):
                if not semantic_model.name:
                    semantic_model.name = entry.name or f"model_{entry.id}"
                if not semantic_model.connector:
                    semantic_model.connector = connector_entry.name
                base_dialect = semantic_model.dialect
            elif isinstance(semantic_model, SemanticModel):
                if not semantic_model.name:
                    semantic_model.name = entry.name or f"model_{entry.id}"
                if not semantic_model.connector:
                    semantic_model.connector = connector_entry.name
                base_dialect = semantic_model.dialect
            dialect = (base_dialect or getattr(sql_connector.DIALECT, "name", "postgres")).lower()
            self._logger.debug(
                "request_id=%s configured tool model=%s connector=%s dialect=%s unified=%s",
                request_id,
                semantic_model.name if hasattr(semantic_model, "name") else str(entry.id),
                connector_entry.name,
                dialect,
                isinstance(semantic_model, UnifiedSemanticModel),
            )

            tool = SqlAnalystTool(
                llm=llm_client,
                semantic_model=semantic_model,
                connector=sql_connector,
                dialect=dialect,
                priority=1 if isinstance(semantic_model, UnifiedSemanticModel) else 0,
                embedder=embedding_provider,
            )
            tools.append(tool)

        if tool_config.allow_sql and not tools:
            raise BusinessValidationError("No semantic models or connectors available for SQL analysis.")

        analyst_agent = (
            AnalystAgent(tools)
            if tools
            else _DisabledAnalystAgent(reason="SQL analyst tools are disabled for this agent.")
        )
        visual_agent = VisualAgent()
        planning_constraints = self._build_planning_constraints(agent_definition, tool_config)
        reasoning_agent = self._build_reasoning_agent(agent_definition)
        planning_context: dict[str, Any] = dict(tool_config.web_search_defaults)
        if conversation_context:
            planning_context["conversation_context"] = conversation_context
        if not planning_context:
            planning_context = None

        supervisor = SupervisorOrchestrator(
            analyst_agent=analyst_agent,
            visual_agent=visual_agent,
            reasoning_agent=reasoning_agent,
        )

        response = await supervisor.handle(
            user_query=msg,
            planning_constraints=planning_constraints,
            planning_context=planning_context,
        )
        summary = await self._summarize_response(
            base_llm,
            msg,
            response,
            request_id=request_id,
            prompt_contract=agent_definition.prompt if agent_definition else None,
            output_schema=agent_definition.output if agent_definition else None,
            guardrails=agent_definition.guardrails if agent_definition else None,
        )
        response["summary"] = summary
        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        self._logger.info("orchestrator.chat complete request_id=%s elapsed_ms=%d", request_id, elapsed_ms)
        return response

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

    async def _summarize_response(
        self,
        chat_model: BaseChatModel,
        question: str,
        response_payload: dict[str, Any],
        *,
        request_id: str | None = None,
        prompt_contract: PromptContract | None = None,
        output_schema: OutputSchema | None = None,
        guardrails: GuardrailConfig | None = None,
    ) -> str:
        """
        Generate a concise natural language summary of the orchestrated response.
        """

        preview = self._render_tabular_preview(response_payload.get("result"))
        viz_summary = self._summarise_visualization(response_payload.get("visualization"))

        prompt_sections = [
            "You are a senior analytics assistant. Summarize the findings for a business stakeholder in 2-3 sentences.",
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
        prompt_sections.append(
            "Highlight the most important metric, call out notable changes or trends, and mention if the dataset is empty."
        )

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
            llm_response = await chat_model.ainvoke(messages)
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

    def _build_reasoning_agent(
        self,
        definition: AgentDefinitionModel | None,
    ) -> ReasoningAgent | None:
        if not definition:
            return None
        max_iterations = max(1, int(definition.execution.max_iterations))
        if definition.execution.mode == ExecutionMode.single_step:
            max_iterations = 1
        return ReasoningAgent(max_iterations=max_iterations, logger=self._logger)

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
