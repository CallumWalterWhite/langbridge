import asyncio
import uuid
from types import SimpleNamespace

import pytest

from langbridge.runtime.events import CollectingAgentEventEmitter
from langbridge.runtime.models import (
    CreateAgentJobRequest,
    JobType,
    LLMConnectionSecret,
    LLMProvider as RuntimeLLMProvider,
    RuntimeAgentDefinition,
    RuntimeMessageRole,
    RuntimeThread,
    RuntimeThreadMessage,
    RuntimeThreadState,
)
from langbridge.runtime.models.metadata import LifecycleState, ManagementMode
from langbridge.runtime.services.agent_execution_service_v2 import AgentExecutionServiceV2


def _run(coro):
    return asyncio.run(coro)


class _FakeLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        if "Choose the next execution mode" in prompt:
            return '{"mode":"context_analysis","reason":"result context is available"}'
        if "Analyze verified Langbridge result data" in prompt:
            return '{"analysis":"Revenue is highest in US.","result":{"columns":["region","revenue"],"rows":[["US",2200]]}}'
        if "Compose the final Langbridge response" in prompt:
            return (
                '{"summary":"Revenue is highest in US.","result":{"columns":["region","revenue"],'
                '"rows":[["US",2200]]},"visualization":null,"research":{},'
                '"answer":"Revenue is highest in US.","diagnostics":{"mode":"test"}}'
            )
        raise AssertionError(f"Unexpected prompt: {prompt[:120]}")

    async def create_embeddings(self, texts, embedding_model=None):
        return [[1.0] for _ in texts]


class _FailingLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        raise RuntimeError("llm down")

    async def create_embeddings(self, texts, embedding_model=None):
        return [[1.0] for _ in texts]


class _ObjectStore:
    def __init__(self, value):
        self.value = value

    async def get_by_id(self, id_):
        return self.value if self.value.id == id_ else None


class _ThreadStore(_ObjectStore):
    async def save(self, instance):
        self.value = instance
        return instance


class _ThreadMessageStore:
    def __init__(self, messages):
        self.messages = list(messages)
        self.added = []

    def add(self, instance):
        self.added.append(instance)
        self.messages.append(instance)
        return instance

    async def list_for_thread(self, thread_id):
        return [message for message in self.messages if message.thread_id == thread_id]


def _ids():
    return SimpleNamespace(
        workspace_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        llm_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
    )


def _agent_definition(ids) -> RuntimeAgentDefinition:
    return RuntimeAgentDefinition(
        id=ids.agent_id,
        name="commerce_agent",
        description="Commerce analyst.",
        llm_connection_id=ids.llm_id,
        definition={
            "features": {"visualization_enabled": True},
            "tools": [
                {
                    "name": "commerce_sql",
                    "tool_type": "sql",
                    "description": "Commerce dataset.",
                    "config": {"dataset_ids": ["commerce_orders"]},
                }
            ],
            "execution": {"max_iterations": 4},
        },
        is_active=True,
        management_mode=ManagementMode.RUNTIME_MANAGED,
        lifecycle_state=LifecycleState.ACTIVE,
    )


def _llm_connection(ids) -> LLMConnectionSecret:
    return LLMConnectionSecret(
        id=ids.llm_id,
        name="test-llm",
        provider=RuntimeLLMProvider.OPENAI,
        model="test-model",
        api_key="test",
        workspace_id=ids.workspace_id,
    )


def _thread(ids) -> RuntimeThread:
    return RuntimeThread(
        id=ids.thread_id,
        workspace_id=ids.workspace_id,
        created_by=ids.actor_id,
        last_message_id=ids.message_id,
        state=RuntimeThreadState.processing,
    )


def _user_message(ids) -> RuntimeThreadMessage:
    return RuntimeThreadMessage(
        id=ids.message_id,
        thread_id=ids.thread_id,
        role=RuntimeMessageRole.user,
        content={
            "text": "Show revenue by region",
            "context": {
                "result": {
                    "columns": ["region", "revenue"],
                    "rows": [["US", 2200]],
                }
            },
        },
    )


def _request(ids) -> CreateAgentJobRequest:
    return CreateAgentJobRequest(
        job_type=JobType.AGENT,
        agent_definition_id=ids.agent_id,
        workspace_id=ids.workspace_id,
        actor_id=ids.actor_id,
        thread_id=ids.thread_id,
    )


def _service(ids, provider) -> tuple[AgentExecutionServiceV2, _ThreadMessageStore]:
    message_store = _ThreadMessageStore([_user_message(ids)])
    return (
        AgentExecutionServiceV2(
            agent_definition_repository=_ObjectStore(_agent_definition(ids)),
            llm_repository=_ObjectStore(_llm_connection(ids)),
            thread_repository=_ThreadStore(_thread(ids)),
            thread_message_repository=message_store,
            llm_provider_factory=lambda connection: provider,
        ),
        message_store,
    )


def test_agent_execution_service_v2_runs_new_ai_flow_and_persists_message() -> None:
    ids = _ids()
    service, message_store = _service(ids, _FakeLLMProvider())
    emitter = CollectingAgentEventEmitter()

    result = _run(
        service.execute(
            job_id=ids.job_id,
            request=_request(ids),
            event_emitter=emitter,
        )
    )

    assert result.response["summary"] == "Revenue is highest in US."
    assert result.ai_run.mode == "direct"
    assert result.thread.state == RuntimeThreadState.awaiting_user_input
    assert result.assistant_message in message_store.added
    assert result.assistant_message.model_snapshot["runtime"] == "langbridge.ai"
    assert result.response["diagnostics"]["ai_run"]["route"] == "direct:analyst.commerce_sql"
    assert [event["event_type"] for event in emitter.events] == [
        "AgentRunStarted",
        "AgentRuntimePrepared",
        "AgentRunCompleted",
    ]


def test_agent_execution_service_v2_aborts_when_llm_provider_errors() -> None:
    ids = _ids()
    service, _ = _service(ids, _FailingLLMProvider())
    emitter = CollectingAgentEventEmitter()

    with pytest.raises(RuntimeError, match="llm down"):
        _run(
            service.execute(
                job_id=ids.job_id,
                request=_request(ids),
                event_emitter=emitter,
            )
        )

    assert emitter.events[-1]["event_type"] == "AgentRunFailed"
