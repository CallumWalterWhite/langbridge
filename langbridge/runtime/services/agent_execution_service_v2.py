"""Runtime agent execution service for the Langbridge AI v1 agent flow."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from langbridge.ai import AgentProfile, LangbridgeAIFactory, MetaControllerRun
from langbridge.ai.llm import create_provider
from langbridge.ai.llm.base import LLMProvider
from langbridge.ai.tools.semantic_search import SemanticSearchTool
from langbridge.ai.tools.sql import SqlAnalysisTool
from langbridge.ai.tools.web_search import WebSearchProvider
from langbridge.runtime.events import AgentEventEmitter, AgentEventVisibility
from langbridge.runtime.models import (
    CreateAgentJobRequest,
    LLMConnectionSecret,
    RuntimeAgentDefinition,
    RuntimeConversationMemoryCategory,
    RuntimeThread,
    RuntimeThreadMessage,
    RuntimeThreadState,
    RuntimeMessageRole,
)
from langbridge.runtime.ports import (
    AgentDefinitionStore,
    ConversationMemoryStore,
    LLMConnectionStore,
    ThreadMessageStore,
    ThreadStore,
)
from langbridge.runtime.services.errors import ExecutionValidationError


LLMProviderFactory = Callable[[LLMConnectionSecret], LLMProvider]


@dataclass(slots=True)
class AgentExecutionResultV2:
    response: dict[str, Any]
    thread: RuntimeThread
    user_message: RuntimeThreadMessage
    assistant_message: RuntimeThreadMessage
    agent_definition: RuntimeAgentDefinition
    ai_run: MetaControllerRun


@dataclass(slots=True)
class AgentExecutionServiceV2Tooling:
    sql_analysis_tools: Mapping[str, Sequence[SqlAnalysisTool]] = field(default_factory=dict)
    semantic_search_tools: Mapping[str, Sequence[SemanticSearchTool]] = field(default_factory=dict)
    web_search_providers: Mapping[str, WebSearchProvider] = field(default_factory=dict)


class AgentExecutionServiceV2:
    """Executes runtime agent jobs through `langbridge.ai`, not old orchestrator."""

    def __init__(
        self,
        *,
        agent_definition_repository: AgentDefinitionStore,
        llm_repository: LLMConnectionStore,
        thread_repository: ThreadStore,
        thread_message_repository: ThreadMessageStore,
        memory_repository: ConversationMemoryStore | None = None,
        tooling: AgentExecutionServiceV2Tooling | None = None,
        llm_provider_factory: LLMProviderFactory = create_provider,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._agent_definition_repository = agent_definition_repository
        self._llm_repository = llm_repository
        self._thread_repository = thread_repository
        self._thread_message_repository = thread_message_repository
        self._memory_repository = memory_repository
        self._tooling = tooling or AgentExecutionServiceV2Tooling()
        self._llm_provider_factory = llm_provider_factory

    async def execute(
        self,
        *,
        job_id: uuid.UUID,
        request: CreateAgentJobRequest,
        event_emitter: AgentEventEmitter | None = None,
    ) -> AgentExecutionResultV2:
        thread, user_message, thread_messages = await self._get_thread_and_last_user_message(
            request.thread_id
        )
        agent_definition = await self._get_agent_definition(request.agent_definition_id)
        llm_connection = await self._get_llm_connection(agent_definition.llm_connection_id)
        user_query = self._extract_user_query(user_message)

        await self._emit(
            event_emitter,
            event_type="AgentRunStarted",
            message="Agent run started.",
            source="agent-execution-v2",
            details={"job_id": str(job_id), "agent_definition_id": str(agent_definition.id)},
        )

        try:
            llm_provider = self._llm_provider_factory(llm_connection)
            profile: AgentProfile = self._build_profile(agent_definition)
            runtime = LangbridgeAIFactory(llm_provider=llm_provider).create_profile_runtime(
                profile,
                sql_analysis_tools=self._tooling.sql_analysis_tools,
                semantic_search_tools=self._tooling.semantic_search_tools,
                web_search_providers=self._tooling.web_search_providers,
            )
            context = await self._build_ai_context(
                thread=thread,
                messages=thread_messages,
                user_message=user_message,
                agent_definition=agent_definition,
            )

            await self._emit(
                event_emitter,
                event_type="AgentRuntimePrepared",
                message="Agent runtime prepared.",
                source="agent-execution-v2",
                details={
                    "profile": profile.model_dump(mode="json"),
                    "agent_count": len(runtime.registry.specifications()),
                },
            )

            ai_run = await runtime.meta_controller.handle(
                question=user_query,
                context=context,
            )
            response = self._response_from_run(ai_run)
            self._persist_ai_state(thread, response)
            self._clear_active_run_metadata(thread)

            assistant_message = self._record_assistant_message(
                thread=thread,
                user_message=user_message,
                response=response,
                agent_id=agent_definition.id,
                ai_run=ai_run,
            )
            await self._thread_repository.save(thread)
            await self._write_memory(
                thread=thread,
                user_query=user_query,
                response=response,
            )
            await self._emit(
                event_emitter,
                event_type="AgentRunCompleted",
                message="Agent run completed.",
                visibility=AgentEventVisibility.public,
                source="agent-execution-v2",
                details={
                    "job_id": str(job_id),
                    "mode": ai_run.mode,
                    "route": ai_run.plan.route,
                },
            )
            return AgentExecutionResultV2(
                response=response,
                thread=thread,
                user_message=user_message,
                assistant_message=assistant_message,
                agent_definition=agent_definition,
                ai_run=ai_run,
            )
        except Exception as exc:
            await self._emit(
                event_emitter,
                event_type="AgentRunFailed",
                message=str(exc),
                visibility=AgentEventVisibility.public,
                source="agent-execution-v2",
                details={"job_id": str(job_id), "error_type": exc.__class__.__name__},
            )
            raise

    async def reset_thread_after_failure(self, *, thread_id: uuid.UUID) -> RuntimeThread | None:
        thread = await self._thread_repository.get_by_id(thread_id)
        if thread is not None:
            self._clear_active_run_metadata(thread)
            self._set_thread_awaiting_user_input(thread)
            thread.updated_at = datetime.now(timezone.utc)
            await self._thread_repository.save(thread)
        return thread

    async def _get_thread_and_last_user_message(
        self,
        thread_id: uuid.UUID,
    ) -> tuple[RuntimeThread, RuntimeThreadMessage, list[RuntimeThreadMessage]]:
        thread = await self._thread_repository.get_by_id(thread_id)
        if thread is None:
            raise ExecutionValidationError(f"Thread with ID {thread_id} does not exist.")

        messages = await self._thread_message_repository.list_for_thread(thread.id)
        if not messages:
            raise ExecutionValidationError(f"Thread {thread.id} has no messages to process.")

        last_message: RuntimeThreadMessage | None = None
        if thread.last_message_id is not None:
            last_message = next((msg for msg in messages if msg.id == thread.last_message_id), None)
        if last_message is None:
            last_message = messages[-1]
        if self._role_value(last_message.role) != RuntimeMessageRole.user.value:
            user_messages = [
                msg for msg in messages if self._role_value(msg.role) == RuntimeMessageRole.user.value
            ]
            if not user_messages:
                raise ExecutionValidationError(f"Thread {thread.id} does not contain a user message.")
            last_message = user_messages[-1]
        return thread, last_message, messages

    async def _get_agent_definition(self, agent_definition_id: uuid.UUID) -> RuntimeAgentDefinition:
        agent_definition = await self._agent_definition_repository.get_by_id(agent_definition_id)
        if agent_definition is None:
            raise ExecutionValidationError(
                f"Agent definition with ID {agent_definition_id} does not exist."
            )
        if not agent_definition.is_active:
            raise ExecutionValidationError(f"Agent definition {agent_definition_id} is not active.")
        return agent_definition

    async def _get_llm_connection(self, llm_connection_id: uuid.UUID) -> LLMConnectionSecret:
        llm_connection = await self._llm_repository.get_by_id(llm_connection_id)
        if llm_connection is None:
            raise ExecutionValidationError(f"LLM connection with ID {llm_connection_id} does not exist.")
        if not llm_connection.is_active:
            raise ExecutionValidationError(f"LLM connection {llm_connection_id} is not active.")
        return llm_connection

    @staticmethod
    def _build_profile(agent_definition: RuntimeAgentDefinition) -> AgentProfile:
        return AgentProfile.from_definition(
            name=agent_definition.name,
            description=agent_definition.description,
            definition=agent_definition.definition or {},
        )

    async def _build_ai_context(
        self,
        *,
        thread: RuntimeThread,
        messages: list[RuntimeThreadMessage],
        user_message: RuntimeThreadMessage,
        agent_definition: RuntimeAgentDefinition,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            "thread": {
                "id": str(thread.id),
                "workspace_id": str(thread.workspace_id),
            },
            "agent_definition": {
                "id": str(agent_definition.id),
                "name": agent_definition.name,
            },
            "conversation_context": self._conversation_context(messages),
        }

        content = user_message.content if isinstance(user_message.content, dict) else {}
        message_context = content.get("context")
        if isinstance(message_context, dict):
            context.update(message_context)
        for key in ("result", "filters", "sources", "mode", "force_web_search", "limit"):
            if key in content:
                context[key] = content[key]

        memories = await self._memory_items(thread.id)
        if memories:
            context["retrieved_memories"] = memories
        return context

    async def _build_sql_analysis_tools(
            self, 
            *,
            llm_provider: LLMProvider,
            agent_profile: AgentProfile) -> Mapping[str, Sequence[SqlAnalysisTool]]:
        if not agent_profile.analyst_scopes:
            return {}
        
        tools: dict[str, list[SqlAnalysisTool]] = {}

        return {}

    async def _memory_items(self, thread_id: uuid.UUID) -> list[dict[str, Any]]:
        if self._memory_repository is None:
            return []
        items = await self._memory_repository.list_for_thread(thread_id, limit=20)
        if not items:
            return []
        await self._memory_repository.touch_items([item.id for item in items if item.id is not None])
        return [
            {
                "id": str(item.id),
                "category": self._role_value(item.category),
                "content": item.content,
                "metadata": dict(item.metadata or {}),
            }
            for item in items
        ]

    @staticmethod
    def _conversation_context(messages: list[RuntimeThreadMessage], *, max_messages: int = 12) -> str:
        lines: list[str] = []
        for message in messages[-max_messages:]:
            text = AgentExecutionServiceV2._message_text(message)
            if not text:
                continue
            lines.append(f"{AgentExecutionServiceV2._role_value(message.role)}: {text}")
        return "\n".join(lines)

    @staticmethod
    def _message_text(message: RuntimeThreadMessage) -> str:
        content = message.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, dict):
            for key in ("text", "message", "prompt", "query", "summary", "answer"):
                value = content.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @staticmethod
    def _extract_user_query(message: RuntimeThreadMessage) -> str:
        text = AgentExecutionServiceV2._message_text(message)
        if text:
            return text
        raise ExecutionValidationError(f"Thread message {message.id} does not contain user text.")

    @staticmethod
    def _response_from_run(ai_run: MetaControllerRun) -> dict[str, Any]:
        response = dict(ai_run.final_result or {})
        diagnostics = response.get("diagnostics")
        response["diagnostics"] = {
            **(diagnostics if isinstance(diagnostics, dict) else {}),
            "ai_run": {
                "mode": ai_run.mode,
                "route": ai_run.plan.route,
                "plan": ai_run.plan.model_dump(mode="json"),
                "verification": [item.model_dump(mode="json") for item in ai_run.verification],
                "review_decisions": [
                    item.model_dump(mode="json") for item in ai_run.review_decisions
                ],
                "diagnostics": dict(ai_run.diagnostics or {}),
            },
        }
        return response

    @staticmethod
    def _persist_ai_state(thread: RuntimeThread, response: dict[str, Any]) -> None:
        diagnostics = response.get("diagnostics")
        metadata = dict(thread.metadata or {})
        if isinstance(diagnostics, dict):
            ai_run = diagnostics.get("ai_run")
            if isinstance(ai_run, dict):
                metadata["last_ai_run"] = {
                    "mode": ai_run.get("mode"),
                    "route": ai_run.get("route"),
                    "diagnostics": ai_run.get("diagnostics"),
                }
        thread.metadata = metadata

    @staticmethod
    def _clear_active_run_metadata(thread: RuntimeThread) -> None:
        metadata = dict(thread.metadata or {})
        metadata.pop("active_run_id", None)
        metadata.pop("active_run_type", None)
        thread.metadata = metadata

    @staticmethod
    def _set_thread_awaiting_user_input(thread: RuntimeThread) -> None:
        thread.state = RuntimeThreadState.awaiting_user_input

    def _record_assistant_message(
        self,
        *,
        thread: RuntimeThread,
        user_message: RuntimeThreadMessage,
        response: dict[str, Any],
        agent_id: uuid.UUID,
        ai_run: MetaControllerRun,
    ) -> RuntimeThreadMessage:
        assistant_message_id = uuid.uuid4()
        assistant_message = RuntimeThreadMessage(
            id=assistant_message_id,
            thread_id=thread.id,
            parent_message_id=user_message.id,
            role=RuntimeMessageRole.assistant,
            content={
                "summary": response.get("summary"),
                "answer": response.get("answer"),
                "result": response.get("result"),
                "visualization": response.get("visualization"),
                "research": response.get("research"),
                "diagnostics": response.get("diagnostics"),
            },
            model_snapshot={
                "agent_id": str(agent_id),
                "runtime": "langbridge.ai",
                "meta_controller_mode": ai_run.mode,
                "route": ai_run.plan.route,
            },
            error=response.get("error") if isinstance(response.get("error"), dict) else None,
        )
        self._thread_message_repository.add(assistant_message)
        thread.last_message_id = assistant_message_id
        self._set_thread_awaiting_user_input(thread)
        thread.updated_at = datetime.now(timezone.utc)
        return assistant_message

    async def _write_memory(
        self,
        *,
        thread: RuntimeThread,
        user_query: str,
        response: dict[str, Any],
    ) -> None:
        if self._memory_repository is None:
            return
        answer = response.get("answer") or response.get("summary")
        if not isinstance(answer, str) or not answer.strip():
            return
        item = self._memory_repository.create_item(
            thread_id=thread.id,
            actor_id=thread.created_by,
            category=RuntimeConversationMemoryCategory.answer.value,
            content=f"User asked: {user_query}\nAssistant answered: {answer.strip()}",
            metadata_json={"runtime": "langbridge.ai"},
        )
        if item is not None:
            await self._memory_repository.flush()

    @staticmethod
    async def _emit(
        event_emitter: AgentEventEmitter | None,
        *,
        event_type: str,
        message: str,
        visibility: AgentEventVisibility = AgentEventVisibility.internal,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if event_emitter is None:
            return
        await event_emitter.emit(
            event_type=event_type,
            message=message,
            visibility=visibility,
            source=source,
            details=details,
        )

    @staticmethod
    def _role_value(role: Any) -> str:
        return str(getattr(role, "value", role))


__all__ = [
    "AgentExecutionResultV2",
    "AgentExecutionServiceV2",
    "AgentExecutionServiceV2Tooling",
]
