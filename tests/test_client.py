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

    result = agent.invoke(capability_name_or_id="cap-id-1", input_data={})
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

    result = agent.invoke(capability_name_or_id="cap-id-1", input_data={})
    assert result.success is True


@respx.mock
def test_sync_invoke_invalid_name_raises_error(sync_client: IntunoClient):
    """Test that invoking with an invalid capability name raises ValueError."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    agents = sync_client.discover(query="test")
    agent = agents[0]

    with pytest.raises(ValueError):
        agent.invoke(capability_name_or_id="invalid-name", input_data={})


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

    result = await agent.ainvoke(capability_name_or_id="cap-id-1", input_data={})
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

    result = await agent.ainvoke(capability_name_or_id="cap-id-1", input_data={})
    assert result.success is True


@pytest.mark.asyncio
@respx.mock
async def test_async_invoke_invalid_name_raises_error(async_client: AsyncIntunoClient):
    """Test that async invoking with an invalid capability name raises ValueError."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    agents = await async_client.discover(query="test")
    agent = agents[0]

    with pytest.raises(ValueError):
        await agent.ainvoke(capability_name_or_id="invalid-name", input_data={})


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
            agent_id="agent-1", capability_id="cap-1", input_data={}
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

    agent.invoke(capability_name_or_id="cap-id-1", input_data={"x": 1})

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
        capability_id="cap-1",
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
        capability_id="cap-1",
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
