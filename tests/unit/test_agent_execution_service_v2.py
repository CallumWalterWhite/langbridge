import asyncio
import uuid
from types import SimpleNamespace

import pytest

from langbridge.runtime.events import CollectingAgentEventEmitter, normalize_agent_stream_stage
from langbridge.runtime.models import (
    CreateAgentJobRequest,
    DatasetColumnMetadata,
    DatasetMetadata,
    JobType,
    LLMConnectionSecret,
    LLMProvider as RuntimeLLMProvider,
    RuntimeAgentDefinition,
    RuntimeConversationMemoryCategory,
    RuntimeConversationMemoryItem,
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
    def __init__(self) -> None:
        self.prompts = []

    async def acomplete(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        if "Decide Langbridge agent route" in prompt:
            return (
                '{"action":"direct","rationale":"Configured analyst can answer from thread context.",'
                '"agent_name":"analyst.commerce_sql","task_kind":"analyst","input":{},'
                '"clarification_question":null,"plan_guidance":null}'
            )
        if "Choose the next execution mode" in prompt:
            return '{"mode":"context_analysis","reason":"result context is available"}'
        if "Analyze verified Langbridge result data" in prompt:
            return '{"analysis":"Revenue is highest in US.","result":{"columns":["region","revenue"],"rows":[["US",2200]]}}'
        if "Review the final Langbridge answer package" in prompt:
            return (
                '{"action":"approve","reason_code":"grounded_complete",'
                '"rationale":"Answer is grounded in the supplied evidence.",'
                '"issues":[],"updated_context":{},"clarification_question":null}'
            )
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


class _SqlLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        if "Decide Langbridge agent route" in prompt:
            return (
                '{"action":"direct","rationale":"Configured analyst can query dataset SQL tool.",'
                '"agent_name":"analyst.commerce_sql","task_kind":"analyst","input":{},'
                '"clarification_question":null,"plan_guidance":null}'
            )
        if "Choose the next execution mode" in prompt:
            return '{"mode":"sql","reason":"dataset SQL tool is available"}'
        if "You are generating dataset-scope SQL" in prompt:
            return "SELECT orders.region, orders.revenue FROM orders"
        if "Summarize verified SQL analysis" in prompt:
            return '{"analysis":"US revenue is 2200."}'
        if "Review the final Langbridge answer package" in prompt:
            return (
                '{"action":"approve","reason_code":"grounded_complete",'
                '"rationale":"Answer is grounded in the supplied evidence.",'
                '"issues":[],"updated_context":{},"clarification_question":null}'
            )
        if "Compose the final Langbridge response" in prompt:
            return (
                '{"summary":"US revenue is 2200.","result":{"columns":["region","revenue"],'
                '"rows":[["US",2200]]},"visualization":null,"research":{},'
                '"answer":"US revenue is 2200.","diagnostics":{"mode":"test"}}'
            )
        raise AssertionError(f"Unexpected prompt: {prompt[:120]}")

    async def create_embeddings(self, texts, embedding_model=None):
        return [[1.0] for _ in texts]


class _ClarificationLLMProvider:
    def __init__(self) -> None:
        self.prompts = []

    async def acomplete(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        if "Decide Langbridge agent route" in prompt:
            return (
                '{"action":"direct","rationale":"Analyst should ask a targeted clarification.",'
                '"agent_name":"analyst.commerce_sql","task_kind":"analyst","input":{},'
                '"clarification_question":null,"plan_guidance":null}'
            )
        if "Choose the next execution mode" in prompt:
            return (
                '{"mode":"clarify","reason":"Time period and ranking metric are missing.",'
                '"clarification_question":"Which time period should I use, and should I rank product categories by total gross margin dollars or by gross margin percentage?"}'
            )
        if "Compose the final Langbridge response" in prompt:
            return (
                '{"summary":"I need one clarification before I can answer.",'
                '"result":{},"visualization":null,"research":{},'
                '"answer":"Which time period should I use, and should I rank product categories by total gross margin dollars or by gross margin percentage?",'
                '"diagnostics":{"mode":"clarification"}}'
            )
        raise AssertionError(f"Unexpected prompt: {prompt[:120]}")

    async def create_embeddings(self, texts, embedding_model=None):
        return [[1.0] for _ in texts]


class _SimpleProfileLLMProvider(_FakeLLMProvider):
    async def acomplete(self, prompt: str, **kwargs):
        if "Decide Langbridge agent route" in prompt:
            return (
                '{"action":"direct","rationale":"Configured analyst can answer from thread context.",'
                '"agent_name":"analyst.commerce_agent","task_kind":"analyst","input":{},'
                '"clarification_question":null,"plan_guidance":null}'
            )
        return await super().acomplete(prompt, **kwargs)


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


class _MemoryStore:
    def __init__(self, items):
        self.items = list(items)
        self.created = []
        self.touched = []
        self.flush_count = 0

    async def list_for_thread(self, thread_id, *, limit=200):
        return [item for item in self.items if item.thread_id == thread_id][:limit]

    def create_item(self, *, thread_id, actor_id, category, content, metadata_json=None):
        item = RuntimeConversationMemoryItem(
            id=uuid.uuid4(),
            thread_id=thread_id,
            actor_id=actor_id,
            category=category,
            content=content,
            metadata=metadata_json or {},
        )
        self.created.append(item)
        self.items.append(item)
        return item

    async def touch_items(self, item_ids):
        self.touched.extend(item_ids)

    async def flush(self):
        self.flush_count += 1


class _DatasetStore:
    def __init__(self, datasets):
        self.datasets = {dataset.id: dataset for dataset in datasets}

    async def get_by_ids(self, dataset_ids):
        return [self.datasets[dataset_id] for dataset_id in dataset_ids if dataset_id in self.datasets]

    async def get_by_ids_for_workspace(self, *, workspace_id, dataset_ids):
        return [
            dataset
            for dataset_id in dataset_ids
            if (dataset := self.datasets.get(dataset_id)) is not None and dataset.workspace_id == workspace_id
        ]


class _DatasetColumnStore:
    def __init__(self, columns_by_dataset):
        self.columns_by_dataset = columns_by_dataset

    async def list_for_dataset(self, *, dataset_id):
        return list(self.columns_by_dataset.get(dataset_id, []))


class _FederatedQueryTool:
    def __init__(self):
        self.calls = []

    async def execute_federated_query(self, payload):
        self.calls.append(payload)
        return {
            "columns": ["region", "revenue"],
            "rows": [{"region": "US", "revenue": 2200}],
            "execution": {"total_runtime_ms": 7},
        }


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


def _dataset_agent_definition(ids, dataset_id: uuid.UUID) -> RuntimeAgentDefinition:
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
                    "config": {"dataset_ids": [str(dataset_id)]},
                }
            ],
            "execution": {"max_iterations": 4},
        },
        is_active=True,
        management_mode=ManagementMode.RUNTIME_MANAGED,
        lifecycle_state=LifecycleState.ACTIVE,
    )


def _simple_ai_agent_definition(ids) -> RuntimeAgentDefinition:
    return RuntimeAgentDefinition(
        id=ids.agent_id,
        name="commerce_agent",
        description="Commerce analyst.",
        llm_connection_id=ids.llm_id,
        definition={
            "analyst_scope": {
                "datasets": ["commerce_orders"],
                "query_policy": "dataset_only",
            },
            "prompts": {"system_prompt": "Answer from verified commerce context."},
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


def _plain_user_message(ids) -> RuntimeThreadMessage:
    return RuntimeThreadMessage(
        id=ids.message_id,
        thread_id=ids.thread_id,
        role=RuntimeMessageRole.user,
        content={"text": "Show revenue by region"},
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
    assert result.ai_run.execution_mode == "direct"
    assert result.ai_run.status == "completed"
    assert result.thread.state == RuntimeThreadState.awaiting_user_input
    assert result.assistant_message in message_store.added
    assert result.assistant_message.model_snapshot["runtime"] == "langbridge.ai"
    assert result.response["diagnostics"]["ai_run"]["route"] == "direct:analyst.commerce_sql"
    assert result.response["diagnostics"]["ai_run"]["execution_mode"] == "direct"
    assert result.response["diagnostics"]["ai_run"]["status"] == "completed"
    event_types = [event["event_type"] for event in emitter.events]
    assert event_types[0] == "AgentRunStarted"
    assert "MetaControllerStarted" in event_types
    assert "AgentRouteSelected" in event_types
    assert "PlanStepStarted" in event_types
    assert "AnalystContextAnalysisStarted" in event_types
    assert "PresentationCompleted" in event_types
    assert event_types[-1] == "AgentRunCompleted"


def test_agent_execution_service_v2_accepts_simple_ai_profile_definition_shape() -> None:
    ids = _ids()
    provider = _SimpleProfileLLMProvider()
    message_store = _ThreadMessageStore([_user_message(ids)])
    service = AgentExecutionServiceV2(
        agent_definition_repository=_ObjectStore(_simple_ai_agent_definition(ids)),
        llm_repository=_ObjectStore(_llm_connection(ids)),
        thread_repository=_ThreadStore(_thread(ids)),
        thread_message_repository=message_store,
        llm_provider_factory=lambda connection: provider,
    )

    result = _run(service.execute(job_id=ids.job_id, request=_request(ids)))

    assert result.response["summary"] == "Revenue is highest in US."
    assert result.response["diagnostics"]["ai_run"]["route"] == "direct:analyst.commerce_agent"


def test_agent_execution_service_v2_restores_and_writes_conversation_memory() -> None:
    ids = _ids()
    provider = _FakeLLMProvider()
    memory_item = RuntimeConversationMemoryItem(
        id=uuid.uuid4(),
        thread_id=ids.thread_id,
        actor_id=ids.actor_id,
        category=RuntimeConversationMemoryCategory.preference,
        content="Prefer gross revenue when user asks for revenue.",
        metadata={"source": "test"},
    )
    memory_store = _MemoryStore([memory_item])
    message_store = _ThreadMessageStore([_user_message(ids)])
    service = AgentExecutionServiceV2(
        agent_definition_repository=_ObjectStore(_agent_definition(ids)),
        llm_repository=_ObjectStore(_llm_connection(ids)),
        thread_repository=_ThreadStore(_thread(ids)),
        thread_message_repository=message_store,
        memory_repository=memory_store,
        llm_provider_factory=lambda connection: provider,
    )

    result = _run(service.execute(job_id=ids.job_id, request=_request(ids)))

    assert result.response["summary"] == "Revenue is highest in US."
    assert memory_item.id in memory_store.touched
    assert any(
        "Prefer gross revenue" in prompt and "Decide Langbridge agent route" in prompt
        for prompt in provider.prompts
    )
    assert any(
        "Prefer gross revenue" in prompt and "Analyze verified Langbridge result data" in prompt
        for prompt in provider.prompts
    )
    created_categories = [item.category for item in memory_store.created]
    assert RuntimeConversationMemoryCategory.answer.value in created_categories
    assert RuntimeConversationMemoryCategory.decision.value in created_categories
    assert memory_store.flush_count == 1


def test_agent_execution_service_v2_passes_requested_agent_mode_to_meta_flow() -> None:
    ids = _ids()
    provider = _FakeLLMProvider()
    service, _ = _service(ids, provider)
    request = _request(ids).model_copy(update={"agent_mode": "context_analysis"})

    result = _run(service.execute(job_id=ids.job_id, request=request))

    assert result.response["summary"] == "Revenue is highest in US."
    assert any("Requested agent mode: context_analysis" in prompt for prompt in provider.prompts)
    assert not any("Choose the next execution mode" in prompt for prompt in provider.prompts)


def test_agent_execution_service_v2_surfaces_specific_clarification_question() -> None:
    ids = _ids()
    provider = _ClarificationLLMProvider()
    message_store = _ThreadMessageStore([_plain_user_message(ids)])
    emitter = CollectingAgentEventEmitter()
    service = AgentExecutionServiceV2(
        agent_definition_repository=_ObjectStore(_agent_definition(ids)),
        llm_repository=_ObjectStore(_llm_connection(ids)),
        thread_repository=_ThreadStore(_thread(ids)),
        thread_message_repository=message_store,
        llm_provider_factory=lambda connection: provider,
    )

    result = _run(service.execute(job_id=ids.job_id, request=_request(ids), event_emitter=emitter))

    question = (
        "Which time period should I use, and should I rank product categories by total gross margin "
        "dollars or by gross margin percentage?"
    )
    assert result.response["summary"] == "I need one clarification before I can answer."
    assert result.response["answer"] == question
    assert result.response["diagnostics"]["clarifying_question"] == question
    assert result.assistant_message.content["answer"] == question
    assert result.assistant_message.content["diagnostics"]["clarifying_question"] == question
    assert emitter.events[-1]["event_type"] == "AgentRunCompleted"
    assert emitter.events[-1]["message"] == question


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


def test_agent_execution_service_v2_auto_builds_sql_tool_from_runtime_catalog() -> None:
    ids = _ids()
    dataset_id = uuid.uuid4()
    dataset = DatasetMetadata(
        id=dataset_id,
        workspace_id=ids.workspace_id,
        connection_id=uuid.uuid4(),
        name="Orders",
        sql_alias="orders",
        dataset_type="TABLE",
        materialization_mode="live",
        source={"table": "orders"},
        source_kind="database",
        storage_kind="table",
        dialect="postgres",
        schema_name="public",
        table_name="orders",
        relation_identity={
            "canonical_reference": f"dataset:{dataset_id}",
            "relation_name": "orders",
            "source_kind": "database",
            "storage_kind": "table",
        },
        execution_capabilities={
            "supports_structured_scan": True,
            "supports_sql_federation": True,
        },
        status="published",
        management_mode=ManagementMode.RUNTIME_MANAGED,
        lifecycle_state=LifecycleState.ACTIVE,
    )
    columns = [
        DatasetColumnMetadata(
            id=uuid.uuid4(),
            dataset_id=dataset_id,
            workspace_id=ids.workspace_id,
            name="region",
            data_type="text",
        ),
        DatasetColumnMetadata(
            id=uuid.uuid4(),
            dataset_id=dataset_id,
            workspace_id=ids.workspace_id,
            name="revenue",
            data_type="integer",
        ),
    ]
    message_store = _ThreadMessageStore([_plain_user_message(ids)])
    federated_query_tool = _FederatedQueryTool()
    emitter = CollectingAgentEventEmitter()
    service = AgentExecutionServiceV2(
        agent_definition_repository=_ObjectStore(_dataset_agent_definition(ids, dataset_id)),
        llm_repository=_ObjectStore(_llm_connection(ids)),
        thread_repository=_ThreadStore(_thread(ids)),
        thread_message_repository=message_store,
        dataset_repository=_DatasetStore([dataset]),
        dataset_column_repository=_DatasetColumnStore({dataset_id: columns}),
        federated_query_tool=federated_query_tool,
        llm_provider_factory=lambda connection: _SqlLLMProvider(),
    )

    result = _run(service.execute(job_id=ids.job_id, request=_request(ids), event_emitter=emitter))

    assert result.response["summary"] == "US revenue is 2200."
    assert result.ai_run.step_results[0]["diagnostics"]["agent_mode"] == "sql"
    assert federated_query_tool.calls[0]["query"] == "SELECT orders.region, orders.revenue FROM orders LIMIT 1000"
    event_types = [event["event_type"] for event in emitter.events]
    assert "AgentToolSelected" in event_types
    assert "SqlGenerationStarted" in event_types
    assert "SqlExecutionStarted" in event_types
    assert "SqlExecutionCompleted" in event_types


def test_ai_event_types_map_to_stream_stages() -> None:
    assert normalize_agent_stream_stage(event_type="SqlGenerationStarted") == "generating_sql"
    assert normalize_agent_stream_stage(event_type="SqlExecutionStarted") == "running_query"
    assert normalize_agent_stream_stage(event_type="WebSearchStarted") == "searching_web"
    assert normalize_agent_stream_stage(event_type="SemanticSearchStarted") == "searching_semantic"
    assert normalize_agent_stream_stage(event_type="ChartingStarted") == "rendering_chart"
    assert normalize_agent_stream_stage(event_type="PresentationStarted") == "composing_response"
