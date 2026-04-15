import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from langbridge.runtime.events import (
    AgentEventVisibility,
    CollectingAgentEventEmitter,
    QueueingAgentStreamEmitter,
)
from langbridge.runtime.models import (
    CreateAgentJobRequest,
    JobType,
    RuntimeMessageRole,
    RuntimeRunStreamEvent,
    RuntimeThread,
    RuntimeThreadMessage,
    RuntimeThreadState,
)

if TYPE_CHECKING:
    from langbridge.runtime.bootstrap.configured_runtime import ConfiguredLocalRuntimeHost


@dataclass(slots=True)
class PreparedAgentRun:
    agent: Any
    actor_id: uuid.UUID
    thread: RuntimeThread
    user_message: RuntimeThreadMessage
    job_id: uuid.UUID


def _consume_detached_task_exception(task: asyncio.Task[Any]) -> None:
    if not task.done():
        return
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        return


class AgentApplication:
    def __init__(self, host: "ConfiguredLocalRuntimeHost") -> None:
        self._host = host

    async def create_agent(self, *args: Any, **kwargs: Any) -> Any:
        async with self._host._runtime_operation_scope() as uow:
            result = await self._host._runtime_host.create_agent(*args, **kwargs)
            if uow is not None:
                await uow.commit()
            return result

    async def ask_agent(
        self,
        *,
        prompt: str,
        agent_name: str | None = None,
        thread_id: uuid.UUID | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        prepared = await self._prepare_agent_run(
            prompt=prompt,
            agent_name=agent_name,
            thread_id=thread_id,
            title=title,
        )
        collector = CollectingAgentEventEmitter()
        try:
            execution = await self._execute_prepared_agent_run(
                prepared=prepared,
                event_emitter=collector,
            )
        except Exception:
            await self._reset_thread_after_failure(thread_id=prepared.thread.id)
            raise
        return self._build_agent_response_payload(
            prepared=prepared,
            execution=execution,
            events=collector.events,
        )

    async def ask_agent_stream(
        self,
        *,
        prompt: str,
        agent_name: str | None = None,
        thread_id: uuid.UUID | None = None,
        title: str | None = None,
    ) -> AsyncIterator[RuntimeRunStreamEvent | None]:
        prepared = await self._prepare_agent_run(
            prompt=prompt,
            agent_name=agent_name,
            thread_id=thread_id,
            title=title,
        )
        sequence = 1
        await self._host._run_streams.open_run(
            run_id=prepared.job_id,
            run_type="agent",
            thread_id=prepared.thread.id,
        )
        await self._host._run_streams.publish(
            RuntimeRunStreamEvent(
                sequence=sequence,
                event="run.started",
                status="in_progress",
                stage="planning",
                message="Run queued. Starting execution.",
                timestamp=datetime.now(timezone.utc),
                run_type="agent",
                run_id=prepared.job_id,
                thread_id=prepared.thread.id,
                job_id=prepared.job_id,
                message_id=prepared.user_message.id,
                visibility=AgentEventVisibility.public.value,
                terminal=False,
                source="runtime",
                details={
                    "agent_name": getattr(prepared.agent.config, "name", None),
                    "user_message_id": str(prepared.user_message.id),
                },
            )
        )
        emitter = QueueingAgentStreamEmitter(
            thread_id=prepared.thread.id,
            job_id=prepared.job_id,
            message_id=prepared.user_message.id,
            enqueue=self._host._run_streams.publish,
            initial_sequence=sequence,
        )

        async def run_execution() -> None:
            try:
                execution = await self._execute_prepared_agent_run(
                    prepared=prepared,
                    event_emitter=emitter,
                )
                payload = self._build_agent_response_payload(prepared=prepared, execution=execution)
                final_event = self._build_terminal_stream_event(
                    sequence=emitter.sequence + 1,
                    event="run.completed",
                    prepared=prepared,
                    execution=execution,
                    payload=payload,
                )
                await self._host._run_streams.publish(final_event)
            except Exception as exc:
                await self._reset_thread_after_failure(thread_id=prepared.thread.id)
                await self._host._run_streams.publish(
                    RuntimeRunStreamEvent(
                        sequence=emitter.sequence + 1,
                        event="run.failed",
                        status="failed",
                        stage="failed",
                        message=str(exc),
                        timestamp=datetime.now(timezone.utc),
                        run_type="agent",
                        run_id=prepared.job_id,
                        thread_id=prepared.thread.id,
                        job_id=prepared.job_id,
                        message_id=prepared.user_message.id,
                        visibility=AgentEventVisibility.public.value,
                        terminal=True,
                        source="runtime",
                        details={"error": str(exc)},
                    )
                )
        task = asyncio.create_task(run_execution())
        task.add_done_callback(_consume_detached_task_exception)
        try:
            stream = await self.stream_run(run_id=prepared.job_id)
            async for event in stream:
                yield event
        finally:
            if task.done():
                try:
                    task.result()
                except Exception:
                    return

    async def stream_run(
        self,
        *,
        run_id: uuid.UUID,
        after_sequence: int = 0,
        heartbeat_interval: float = 10.0,
    ) -> AsyncIterator[RuntimeRunStreamEvent | None]:
        return await self._host._run_streams.subscribe(
            run_id=run_id,
            after_sequence=after_sequence,
            heartbeat_interval=heartbeat_interval,
        )

    async def list_agents(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for name, record in self._host._agents.items():
            definition = dict(record.agent_definition.definition or {})
            tools = definition.get("tools") if isinstance(definition.get("tools"), list) else []
            items.append(
                {
                    "id": record.id,
                    "name": name,
                    "description": record.config.description or record.agent_definition.description,
                    "default": self._host._default_agent is not None and self._host._default_agent.id == record.id,
                    "llm_connection": record.config.llm_connection,
                    "tool_count": len(tools),
                    "tools": [
                        {
                            "name": item.get("name"),
                            "tool_type": item.get("tool_type"),
                            "description": item.get("description"),
                        }
                        for item in tools
                        if isinstance(item, dict)
                    ],
                }
            )
        items.sort(key=lambda item: (not bool(item["default"]), str(item["name"]).lower()))
        return items

    async def get_agent(
        self,
        *,
        agent_ref: str,
    ) -> dict[str, Any]:
        record = self._host._resolve_agent_record(agent_ref)
        items = await self.list_agents()
        summary = next((item for item in items if item["id"] == record.id), None) or {}
        return {
            **summary,
            "definition": dict(record.agent_definition.definition or {}),
            "semantic_model": record.config.semantic_model,
            "dataset": record.config.dataset,
            "instructions": record.config.instructions,
        }

    async def _prepare_agent_run(
        self,
        *,
        prompt: str,
        agent_name: str | None,
        thread_id: uuid.UUID | None,
        title: str | None,
    ) -> PreparedAgentRun:
        agent = self._host._resolve_agent(agent_name)
        actor_id = self._host._resolve_actor_id()
        job_id = uuid.uuid4()
        timestamp = datetime.now(timezone.utc)
        async with self._host._runtime_operation_scope() as uow:
            existing_thread = None
            if thread_id is not None:
                existing_thread = await self._host._thread_repository.get_by_id(thread_id)
                if existing_thread is None:
                    raise ValueError(f"Thread '{thread_id}' was not found.")
                if existing_thread.workspace_id != self._host.context.workspace_id:
                    raise ValueError("Thread does not belong to the current runtime workspace.")
            if existing_thread is None:
                thread_id = uuid.uuid4()
                thread = RuntimeThread(
                    id=thread_id,
                    workspace_id=self._host.context.workspace_id,
                    title=str(title or "").strip() or agent.config.name,
                    created_by=actor_id,
                    state=RuntimeThreadState.processing,
                    metadata={
                        "runtime_mode": "local_config",
                        "active_run_id": str(job_id),
                        "active_run_type": "agent",
                    },
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                thread = self._host._thread_repository.add(thread)
            else:
                thread = existing_thread
                thread.state = RuntimeThreadState.processing
                thread.updated_at = timestamp
                metadata = dict(thread.metadata or {})
                metadata["active_run_id"] = str(job_id)
                metadata["active_run_type"] = "agent"
                thread.metadata = metadata
                if str(title or "").strip():
                    thread.title = str(title).strip()
                await self._host._thread_repository.save(thread)

            user_message = RuntimeThreadMessage(
                id=uuid.uuid4(),
                thread_id=thread_id,
                role=RuntimeMessageRole.user,
                content={"text": str(prompt or "").strip()},
                created_at=timestamp,
            )
            user_message = self._host._thread_message_repository.add(user_message)
            thread.last_message_id = user_message.id
            await self._host._thread_repository.save(thread)
            if uow is not None:
                await uow.commit()

        return PreparedAgentRun(
            agent=agent,
            actor_id=actor_id,
            thread=thread,
            user_message=user_message,
            job_id=job_id,
        )

    async def _execute_prepared_agent_run(
        self,
        *,
        prepared: PreparedAgentRun,
        event_emitter,
    ) -> Any:
        async with self._host._runtime_operation_scope() as uow:
            execution = await self._host._runtime_host.create_agent(
                job_id=prepared.job_id,
                request=CreateAgentJobRequest(
                    job_type=JobType.AGENT,
                    agent_definition_id=prepared.agent.id,
                    workspace_id=self._host.context.workspace_id,
                    actor_id=prepared.actor_id,
                    thread_id=prepared.thread.id,
                ),
                event_emitter=event_emitter,
            )
            if uow is not None:
                await uow.commit()
            return execution

    async def _reset_thread_after_failure(self, *, thread_id: uuid.UUID) -> None:
        async with self._host._runtime_operation_scope() as uow:
            await self._host._runtime_host.services.agent_execution.reset_thread_after_failure(
                thread_id=thread_id
            )
            if uow is not None:
                await uow.commit()

    def _build_agent_response_payload(
        self,
        *,
        prepared: PreparedAgentRun,
        execution: Any,
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        response = getattr(execution, "response", {}) or {}
        assistant_message = getattr(execution, "assistant_message", None)
        return {
            "thread_id": prepared.thread.id,
            "run_id": prepared.job_id,
            "job_id": prepared.job_id,
            "message_id": getattr(assistant_message, "id", None),
            "summary": response.get("summary"),
            "result": response.get("result"),
            "visualization": response.get("visualization"),
            "error": response.get("error"),
            "events": list(events or []),
        }

    def _build_terminal_stream_event(
        self,
        *,
        sequence: int,
        event: str,
        prepared: PreparedAgentRun,
        execution: Any,
        payload: dict[str, Any],
    ) -> RuntimeRunStreamEvent:
        response = getattr(execution, "response", {}) or {}
        diagnostics = response.get("diagnostics") if isinstance(response, dict) else None
        analyst_outcome = diagnostics.get("analyst_outcome") if isinstance(diagnostics, dict) else None
        outcome_status = (
            str(analyst_outcome.get("status")).strip().lower()
            if isinstance(analyst_outcome, dict) and analyst_outcome.get("status")
            else ""
        )
        if outcome_status in {"access_denied", "invalid_request", "query_error", "execution_error"}:
            status = "failed"
            stage = outcome_status
            event_name = "run.failed"
        elif outcome_status == "empty_result":
            status = "completed"
            stage = "empty_result"
            event_name = event
        else:
            status = "completed"
            stage = "completed"
            event_name = event
        return RuntimeRunStreamEvent(
            sequence=sequence,
            event=event_name,
            status=status,
            stage=stage,
            message=str(payload.get("summary") or "Run completed."),
            timestamp=datetime.now(timezone.utc),
            run_type="agent",
            run_id=prepared.job_id,
            thread_id=prepared.thread.id,
            job_id=prepared.job_id,
            message_id=payload.get("message_id"),
            visibility=AgentEventVisibility.public.value,
            terminal=True,
            source="runtime",
            details={
                "outcome_status": outcome_status or None,
                "result_available": payload.get("result") is not None,
                "visualization_available": payload.get("visualization") is not None,
                "error": payload.get("error"),
            },
        )
