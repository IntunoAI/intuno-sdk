"""Tests for the Intuno SDK client."""

import pytest
import respx
from httpx import Response

from src.intuno_sdk import AsyncIntunoClient, IntunoClient
from src.intuno_sdk.constants import DEFAULT_BASE_URL
from src.intuno_sdk.exceptions import (
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
        "agentId": "agent-1",
        "name": "Test Agent 1",
        "description": "A test agent",
        "version": "1.0",
        "tags": ["test"],
        "isActive": True,
        "capabilities": [
            {
                "id": "cap-id-1",
                "name": "cap-name-1",
                "description": "A test capability",
                "inputSchema": {},
                "outputSchema": {},
            }
        ],
    }
]
MOCK_INVOKE_RESPONSE = {
    "success": True,
    "data": {"result": "ok"},
    "error": None,
    "latencyMs": 100,
    "statusCode": 200,
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
def test_sync_invoke_via_agent_by_name(sync_client: IntunoClient):
    """Test successful sync invocation via the agent model by capability name."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    agents = sync_client.discover(query="test")
    agent = agents[0]

    result = agent.invoke(capability_name_or_id="cap-name-1", input_data={})
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
async def test_async_invoke_via_agent_by_name(async_client: AsyncIntunoClient):
    """Test successful async invocation via the agent model by capability name."""
    respx.get(f"{BASE_URL}/registry/discover").mock(
        return_value=Response(200, json=MOCK_AGENT_RESPONSE)
    )
    respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=MOCK_INVOKE_RESPONSE)
    )

    agents = await async_client.discover(query="test")
    agent = agents[0]

    result = await agent.ainvoke(capability_name_or_id="cap-name-1", input_data={})
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
    mock_response = {"success": False, "error": "Agent not found", "statusCode": 404}
    respx.post(f"{BASE_URL}/broker/invoke").mock(
        return_value=Response(200, json=mock_response)
    )

    with pytest.raises(InvocationError):
        await async_client.ainvoke(
            agent_id="agent-1", capability_id="cap-1", input_data={}
        )
