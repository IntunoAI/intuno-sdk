"""Tests for the Intuno SDK client."""

import pytest
import respx
from httpx import Response

from intuno_sdk import AsyncIntunoClient, IntunoClient
from intuno_sdk.constants import DEFAULT_BASE_URL
from intuno_sdk.exceptions import (
    APIKeyMissingError,
    AuthenticationError,
    InvocationError,
    IntunoError,
)
from intuno_sdk.models import WorkflowDef, WorkflowStepDef

# --- Constants ---
BASE_URL = DEFAULT_BASE_URL
API_KEY = "test-api-key"
MOCK_AGENT_RESPONSE = [
    {
        "id": "uuid-1",
        "agent_id": "agent-1",
        "name": "Test Agent 1",
        "description": "A test agent",
        "version": "1.0",
        "tags": ["test"],
        "is_active": True,
        "trust_verification": "self-signed",
        "capabilities": [
            {
                "id": "cap-id-1",
                "input_schema": {},
                "output_schema": {},
                "auth_type": {"type": "none"},
            }
        ],
    }
]
MOCK_INVOKE_RESPONSE = {
    "success": True,
    "data": {"result": "ok"},
    "error": None,
    "latency_ms": 100,
    "status_code": 200,
}

# --- Fixtures ---


@pytest.fixture
def sync_client():
    return IntunoClient(api_key=API_KEY)


@pytest.fixture
def async_client():
    return AsyncIntunoClient(api_key=API_KEY)


# --- Initialization Tests ---


def test_init_requires_api_key():
    """Test that initializing clients without an API key raises an error."""
    with pytest.raises(APIKeyMissingError):
        IntunoClient(api_key="")
    with pytest.raises(APIKeyMissingError):
        AsyncIntunoClient(api_key="")


# --- Synchronous Client Tests ---


@respx.mock
def test_sync_discover_success(sync_client: IntunoClient):
    """Test successful agent discovery with the synchronous client."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )

    agents = sync_client.discover(query="test")

    assert len(agents) == 1
    agent = agents[0]
    assert agent.name == "Test Agent 1"
    assert agent._client is sync_client  # Check client injection


@respx.mock
def test_sync_invoke_via_agent_by_id_from_discover(sync_client: IntunoClient):
    """Test successful sync invocation via the agent model by capability ID from discover."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    agents = sync_client.discover(query="test")
    agent = agents[0]

    result = agent.invoke(input_data={})
    assert result.success is True
    assert result.data == {"result": "ok"}


@respx.mock
def test_sync_invoke_via_agent_by_id(sync_client: IntunoClient):
    """Test successful sync invocation via the agent model by capability ID."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    agents = sync_client.discover(query="test")
    agent = agents[0]

    result = agent.invoke(input_data={})
    assert result.success is True


@respx.mock
def test_sync_discover_auth_error(sync_client: IntunoClient):
    """Test that a 401 on sync discover raises AuthenticationError."""
    respx.get(f"{BASE_URL}/registry/discover").mock(return_value=Response(401))
    with pytest.raises(AuthenticationError):
        sync_client.discover(query="test")


# --- Asynchronous Client Tests ---


@pytest.mark.asyncio
@respx.mock
async def test_async_discover_success(async_client: AsyncIntunoClient):
    """Test successful agent discovery with the asynchronous client."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )

    agents = await async_client.discover(query="test")

    assert len(agents) == 1
    agent = agents[0]
    assert agent.name == "Test Agent 1"
    assert agent._client is async_client  # Check client injection


@pytest.mark.asyncio
@respx.mock
async def test_async_invoke_via_agent_by_id_from_discover(async_client: AsyncIntunoClient):
    """Test successful async invocation via the agent model by capability ID from discover."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    agents = await async_client.discover(query="test")
    agent = agents[0]

    result = await agent.ainvoke(input_data={})
    assert result.success is True
    assert result.data == {"result": "ok"}


@pytest.mark.asyncio
@respx.mock
async def test_async_invoke_via_agent_by_id(async_client: AsyncIntunoClient):
    """Test successful async invocation via the agent model by capability ID."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    agents = await async_client.discover(query="test")
    agent = agents[0]

    result = await agent.ainvoke(input_data={})
    assert result.success is True


@pytest.mark.asyncio
@respx.mock
async def test_async_invoke_broker_failure_raises_invocation_error(
    async_client: AsyncIntunoClient,
):
    """Test that a failed but valid broker response raises InvocationError."""
    mock_response = {"success": False, "error": "Agent not found", "latency_ms": 10, "status_code": 404}
    respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=mock_response)
    )

    with pytest.raises(InvocationError):
        await async_client.ainvoke(
            agent_id="agent-1", input_data={}
        )


# --- Agent.invoke sends agent_id (not internal UUID) ---


@respx.mock
def test_invoke_sends_agent_id_not_uuid(sync_client: IntunoClient):
    """Verify that Agent.invoke() sends agent_id (string id), not internal UUID."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    route = respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    agents = sync_client.discover(query="test")
    agent = agents[0]
    assert agent.id == "uuid-1"
    assert agent.agent_id == "agent-1"

    agent.invoke(input_data={"x": 1})

    sent_body = route.calls[0].request.content
    import json
    payload = json.loads(sent_body)
    assert payload["agent_id"] == "agent-1", f"Expected agent_id='agent-1', got '{payload['agent_id']}'"


# --- Invoke with multi-user params ---


@respx.mock
def test_sync_invoke_with_external_user_id(sync_client: IntunoClient):
    """Test that invoke passes conversation_id and external_user_id to the broker."""
    route = respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    result = sync_client.invoke(
        agent_id="agent-1",
        input_data={"x": 1},
        conversation_id="conv-123",
        external_user_id="user-alice",
    )
    assert result.success is True

    import json
    payload = json.loads(route.calls[0].request.content)
    assert payload["conversation_id"] == "conv-123"
    assert payload["external_user_id"] == "user-alice"


@pytest.mark.asyncio
@respx.mock
async def test_async_invoke_with_external_user_id(async_client: AsyncIntunoClient):
    """Test that ainvoke passes external_user_id to the broker."""
    route = respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    result = await async_client.ainvoke(
        agent_id="agent-1",
        input_data={"x": 1},
        external_user_id="user-bob",
    )
    assert result.success is True

    import json
    payload = json.loads(route.calls[0].request.content)
    assert payload["external_user_id"] == "user-bob"


# --- Task API ---


MOCK_TASK_SYNC_RESPONSE = {
    "id": "task-uuid-1",
    "status": "completed",
    "goal": "add numbers",
    "input": {"a": 1, "b": 2},
    "result": {"answer": 3},
    "error_message": None,
    "steps": [],
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:01Z",
}

MOCK_TASK_ASYNC_RESPONSE = {"task_id": "task-uuid-2"}

MOCK_TASK_POLL_RESPONSE = {
    "id": "task-uuid-2",
    "status": "completed",
    "goal": "multiply",
    "input": {},
    "result": {"answer": 42},
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:05Z",
}


@respx.mock
def test_sync_create_task(sync_client: IntunoClient):
    """Test synchronous task creation."""
    respx.post(f"{BASE_URL}/tasks").mock(
        return_value=Response(201, json=MOCK_TASK_SYNC_RESPONSE)
    )

    task = sync_client.create_task(goal="add numbers", input_data={"a": 1, "b": 2})
    assert task.status == "completed"
    assert task.result == {"answer": 3}


@respx.mock
def test_sync_get_task(sync_client: IntunoClient):
    """Test polling task status."""
    respx.get(f"{BASE_URL}/tasks/task-uuid-2").mock(
        return_value=Response(200, json=MOCK_TASK_POLL_RESPONSE)
    )

    task = sync_client.get_task("task-uuid-2")
    assert task.status == "completed"
    assert task.id == "task-uuid-2"


@pytest.mark.asyncio
@respx.mock
async def test_async_create_task(async_client: AsyncIntunoClient):
    """Test async task creation (202 accepted pattern)."""
    respx.post(f"{BASE_URL}/tasks").mock(
        return_value=Response(202, json=MOCK_TASK_ASYNC_RESPONSE)
    )

    task = await async_client.create_task(goal="multiply", async_mode=True)
    assert task.status == "pending"
    assert task.id == "task-uuid-2"


@pytest.mark.asyncio
@respx.mock
async def test_async_get_task(async_client: AsyncIntunoClient):
    """Test async task polling."""
    respx.get(f"{BASE_URL}/tasks/task-uuid-2").mock(
        return_value=Response(200, json=MOCK_TASK_POLL_RESPONSE)
    )

    task = await async_client.get_task("task-uuid-2")
    assert task.status == "completed"
    assert task.result == {"answer": 42}


# --- Workflow API ---

MOCK_WORKFLOW_DEF = WorkflowDef(
    name="test-workflow",
    steps=[
        WorkflowStepDef(id="step1", agent="my-agent", input={"prompt": "hello"}),
    ],
)

MOCK_WORKFLOW_RESPONSE = {
    "id": "wf-uuid-1",
    "name": "test-workflow",
    "version": 1,
    "owner_id": "user-uuid-1",
    "definition": {"name": "test-workflow", "steps": [{"id": "step1", "agent": "my-agent"}]},
    "triggers": None,
    "recovery": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}

MOCK_EXECUTION_RESPONSE = {
    "id": "exec-uuid-1",
    "workflow_id": "wf-uuid-1",
    "status": "running",
    "trigger_data": {"key": "value"},
    "context_id": "ctx-uuid-1",
    "parent_execution_id": None,
    "started_at": "2026-01-01T00:00:00Z",
    "completed_at": None,
    "error": None,
}

MOCK_PROCESS_TABLE = [
    {
        "id": "pe-uuid-1",
        "execution_id": "exec-uuid-1",
        "step_id": "step1",
        "type": "agent",
        "target_id": "agent-uuid-1",
        "target_name": "my-agent",
        "status": "completed",
        "input": None,
        "output": {"result": "ok"},
        "error": None,
        "attempt": 1,
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:00:01Z",
        "duration_ms": 1000,
        "tokens_used": None,
        "cost": None,
    }
]


@respx.mock
def test_sync_create_workflow(sync_client: IntunoClient):
    """Test synchronous workflow creation."""
    respx.post(f"{BASE_URL}/workflows").mock(
        return_value=Response(201, json=MOCK_WORKFLOW_RESPONSE)
    )

    wf = sync_client.create_workflow(MOCK_WORKFLOW_DEF)
    assert wf.id == "wf-uuid-1"
    assert wf.name == "test-workflow"
    assert wf.version == 1


@respx.mock
def test_sync_get_workflow(sync_client: IntunoClient):
    """Test synchronous workflow get."""
    respx.get(f"{BASE_URL}/workflows/wf-uuid-1").mock(
        return_value=Response(200, json=MOCK_WORKFLOW_RESPONSE)
    )

    wf = sync_client.get_workflow("wf-uuid-1")
    assert wf.id == "wf-uuid-1"


@respx.mock
def test_sync_list_workflows(sync_client: IntunoClient):
    """Test synchronous workflow listing."""
    respx.get(f"{BASE_URL}/workflows").mock(
        return_value=Response(200, json=[MOCK_WORKFLOW_RESPONSE])
    )

    workflows = sync_client.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].name == "test-workflow"


@respx.mock
def test_sync_run_workflow(sync_client: IntunoClient):
    """Test triggering a workflow execution."""
    respx.post(f"{BASE_URL}/workflows/wf-uuid-1/run").mock(
        return_value=Response(201, json=MOCK_EXECUTION_RESPONSE)
    )

    execution = sync_client.run_workflow("wf-uuid-1", trigger_data={"key": "value"})
    assert execution.id == "exec-uuid-1"
    assert execution.status == "running"


@respx.mock
def test_sync_get_execution(sync_client: IntunoClient):
    """Test getting execution status."""
    respx.get(f"{BASE_URL}/executions/exec-uuid-1").mock(
        return_value=Response(200, json=MOCK_EXECUTION_RESPONSE)
    )

    execution = sync_client.get_execution("exec-uuid-1")
    assert execution.workflow_id == "wf-uuid-1"


@respx.mock
def test_sync_cancel_execution(sync_client: IntunoClient):
    """Test cancelling an execution."""
    cancelled = dict(MOCK_EXECUTION_RESPONSE, status="cancelled")
    respx.post(f"{BASE_URL}/executions/exec-uuid-1/cancel").mock(
        return_value=Response(200, json=cancelled)
    )

    execution = sync_client.cancel_execution("exec-uuid-1")
    assert execution.status == "cancelled"


@respx.mock
def test_sync_get_process_table(sync_client: IntunoClient):
    """Test retrieving the process table."""
    respx.get(f"{BASE_URL}/executions/exec-uuid-1/ps").mock(
        return_value=Response(200, json=MOCK_PROCESS_TABLE)
    )

    entries = sync_client.get_process_table("exec-uuid-1")
    assert len(entries) == 1
    assert entries[0].step_id == "step1"
    assert entries[0].status == "completed"


@respx.mock
def test_sync_get_workflow_not_found(sync_client: IntunoClient):
    """Test that 404 on get_workflow raises IntunoError."""
    respx.get(f"{BASE_URL}/workflows/bad-id").mock(return_value=Response(404))
    with pytest.raises(IntunoError):
        sync_client.get_workflow("bad-id")


@respx.mock
def test_sync_get_execution_not_found(sync_client: IntunoClient):
    """Test that 404 on get_execution raises IntunoError."""
    respx.get(f"{BASE_URL}/executions/bad-id").mock(return_value=Response(404))
    with pytest.raises(IntunoError):
        sync_client.get_execution("bad-id")


# --- Async workflow tests ---


@pytest.mark.asyncio
@respx.mock
async def test_async_create_workflow(async_client: AsyncIntunoClient):
    """Test async workflow creation."""
    respx.post(f"{BASE_URL}/workflows").mock(
        return_value=Response(201, json=MOCK_WORKFLOW_RESPONSE)
    )

    wf = await async_client.create_workflow(MOCK_WORKFLOW_DEF)
    assert wf.id == "wf-uuid-1"
    assert wf.name == "test-workflow"


@pytest.mark.asyncio
@respx.mock
async def test_async_run_workflow(async_client: AsyncIntunoClient):
    """Test async workflow trigger."""
    respx.post(f"{BASE_URL}/workflows/wf-uuid-1/run").mock(
        return_value=Response(201, json=MOCK_EXECUTION_RESPONSE)
    )

    execution = await async_client.run_workflow("wf-uuid-1", trigger_data={"env": "test"})
    assert execution.id == "exec-uuid-1"
    assert execution.status == "running"


@pytest.mark.asyncio
@respx.mock
async def test_async_get_execution(async_client: AsyncIntunoClient):
    """Test async execution status polling."""
    respx.get(f"{BASE_URL}/executions/exec-uuid-1").mock(
        return_value=Response(200, json=MOCK_EXECUTION_RESPONSE)
    )

    execution = await async_client.get_execution("exec-uuid-1")
    assert execution.workflow_id == "wf-uuid-1"


@pytest.mark.asyncio
@respx.mock
async def test_async_cancel_execution(async_client: AsyncIntunoClient):
    """Test async execution cancellation."""
    cancelled = dict(MOCK_EXECUTION_RESPONSE, status="cancelled")
    respx.post(f"{BASE_URL}/executions/exec-uuid-1/cancel").mock(
        return_value=Response(200, json=cancelled)
    )

    execution = await async_client.cancel_execution("exec-uuid-1")
    assert execution.status == "cancelled"


@pytest.mark.asyncio
@respx.mock
async def test_async_get_process_table(async_client: AsyncIntunoClient):
    """Test async process table retrieval."""
    respx.get(f"{BASE_URL}/executions/exec-uuid-1/ps").mock(
        return_value=Response(200, json=MOCK_PROCESS_TABLE)
    )

    entries = await async_client.get_process_table("exec-uuid-1")
    assert len(entries) == 1
    assert entries[0].step_id == "step1"


@pytest.mark.asyncio
@respx.mock
async def test_async_list_workflows(async_client: AsyncIntunoClient):
    """Test async workflow listing."""
    respx.get(f"{BASE_URL}/workflows").mock(
        return_value=Response(200, json=[MOCK_WORKFLOW_RESPONSE])
    )

    workflows = await async_client.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].id == "wf-uuid-1"
