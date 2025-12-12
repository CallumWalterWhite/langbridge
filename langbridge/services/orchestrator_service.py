
import logging
import time
import uuid
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from connectors.config import ConnectorRuntimeType
from errors.application_errors import BusinessValidationError
from orchestrator.agents.analyst import AnalystAgent
from orchestrator.agents.visual import VisualAgent
from orchestrator.agents.supervisor import SupervisorOrchestrator
from orchestrator.tools.sql_analyst import SqlAnalystTool, load_semantic_model
from orchestrator.tools.sql_analyst.interfaces import LLMClient, SemanticModel, UnifiedSemanticModel
from services.agent_service import AgentService
from services.connector_service import ConnectorService
from services.organization_service import OrganizationService
from services.semantic_model_service import SemanticModelService
from utils.embedding_provider import EmbeddingProvider, EmbeddingProviderError

from models.llm_connections import LLMConnectionSecretResponse
from models.connectors import ConnectorResponse


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
        self._logger = logging.getLogger(__name__)

    async def chat(self, msg: str) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        start_ts = time.perf_counter()
        self._logger.info("orchestrator.chat start request_id=%s", request_id)
        llm_connections = await self._agent_service.list_llm_connection_secrets()
        if not llm_connections:
            raise BusinessValidationError("No LLM connections configured")
        llm_connection: LLMConnectionSecretResponse = llm_connections[0]
        self._logger.debug(
            "request_id=%s using llm_connection id=%s model=%s",
            request_id,
            llm_connection.id,
            llm_connection.model,
        )
        base_llm: BaseChatModel = ChatOpenAI(
            model=llm_connection.model,
            temperature=0.1,
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

        semantic_entries = await self._semantic_model_service.list_all_models()
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

        for entry in semantic_entries:
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

        if not tools:
            raise BusinessValidationError("No semantic models or connectors available for SQL analysis.")

        analyst_agent = AnalystAgent(tools)
        visual_agent = VisualAgent()

        supervisor = SupervisorOrchestrator(
            analyst_agent=analyst_agent,
            visual_agent=visual_agent,
        )

        response = await supervisor.handle(user_query=msg)
        summary = await self._summarize_response(base_llm, msg, response, request_id=request_id)
        response["summary"] = summary
        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        self._logger.info("orchestrator.chat complete request_id=%s elapsed_ms=%d", request_id, elapsed_ms)
        return response

    async def _summarize_response(
        self,
        chat_model: BaseChatModel,
        question: str,
        response_payload: dict[str, Any],
        *,
        request_id: str | None = None,
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
        prompt_sections.append(
            "Highlight the most important metric, call out notable changes or trends, and mention if the dataset is empty."
        )

        prompt = "\n\n".join(prompt_sections)

        try:
            llm_response = await chat_model.ainvoke([HumanMessage(content=prompt)])
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
        return summary_text

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
