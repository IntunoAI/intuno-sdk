"""Tests for the Intuno SDK integrations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from intuno_sdk.integrations.langchain import (
    create_discovery_tool,
    create_network_tools,
    create_task_tool,
    make_tools_from_agent,
)
from intuno_sdk.integrations.openai import (
    execute_network_tool,
    get_a2a_tools,
    get_discovery_tool_openai_schema,
    get_network_tools,
    get_task_tool_openai_schema,
    make_openai_tools_from_agent,
)
from intuno_sdk.models import Agent

# --- Fixtures ---


@pytest.fixture
def mock_agent() -> Agent:
    """Returns a mock Agent object for testing."""
    agent = Agent(
        id="uuid-1",
        agent_id="agent:test:sample:1",
        name="Test Agent",
        description="A test agent",
        tags=["test"],
        is_active=True,
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "integer", "description": "the x param"}},
            "required": ["x"],
        },
    )
    return agent


# --- LangChain Integration Tests ---


def test_create_task_tool():
    """Test the creation of the LangChain create_task tool."""
    mock_client = MagicMock()
    mock_task = MagicMock()
    mock_task.status = "completed"
    mock_task.result = {"answer": "21°C"}
    mock_task.error_message = None
    mock_client.create_task.return_value = mock_task

    # create_task_tool type-checks on IntunoClient, so mock the class attribute check.
    from intuno_sdk import IntunoClient
    mock_client.__class__ = IntunoClient

    tool = create_task_tool(mock_client)
    assert tool.name == "intuno_create_task"
    assert "Delegates a task" in tool.description

    result = tool.func(goal="Get the weather in CDMX")
    mock_client.create_task.assert_called_once_with(goal="Get the weather in CDMX")
    assert "21°C" in result


def test_create_discovery_tool():
    """Test the creation of the LangChain discovery tool."""
    from intuno_sdk import IntunoClient

    mock_client = MagicMock()
    mock_client.discover.return_value = []
    mock_client.__class__ = IntunoClient

    tool = create_discovery_tool(mock_client)
    assert tool.name == "intuno_agent_discovery"
    assert "Searches the Intuno Agent Network" in tool.description

    tool.func(query="test query")
    mock_client.discover.assert_called_once_with(query="test query")


def test_make_tools_from_agent(mock_agent: Agent):
    """Test converting an agent's input schema to a LangChain tool."""
    tools = make_tools_from_agent(mock_agent)

    assert len(tools) == 1
    tool = tools[0]
    assert tool.description == "A test agent"
    assert tool.args_schema is not None

    # Tool name is sanitized from agent_id (colons/dashes → underscores).
    assert tool.name == "agent_test_sample_1"


def test_create_network_tools_returns_three_tools():
    """Test that create_network_tools returns the expected LangChain tools."""
    from intuno_sdk import IntunoClient

    mock_client = MagicMock()
    mock_client.__class__ = IntunoClient

    tools = create_network_tools(mock_client, agent_name="my-agent")
    tool_names = sorted(t.name for t in tools)
    assert tool_names == ["intuno_call_agent", "intuno_import_a2a_agent", "intuno_send_message"]


# --- OpenAI Integration Tests ---


def test_get_task_tool_openai_schema():
    """Test the generation of the OpenAI create_task tool schema."""
    schema = get_task_tool_openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "intuno_create_task"
    assert "goal" in schema["function"]["parameters"]["properties"]
    assert "goal" in schema["function"]["parameters"]["required"]


def test_get_discovery_tool_openai_schema():
    """Test the generation of the OpenAI discovery tool schema."""
    schema = get_discovery_tool_openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "intuno_agent_discovery"
    assert "query" in schema["function"]["parameters"]["properties"]


def test_make_openai_tools_from_agent(mock_agent: Agent):
    """Test converting an agent to an OpenAI tool definition."""
    tools = make_openai_tools_from_agent(mock_agent)

    assert len(tools) == 1
    tool = tools[0]
    assert tool["type"] == "function"
    fn = tool["function"]
    assert fn["description"] == "A test agent"
    assert "x" in fn["parameters"]["properties"]


def test_get_network_tools_shape():
    """Network tools should include discover, call, and send."""
    tools = get_network_tools()
    names = [t["function"]["name"] for t in tools]
    assert names == ["intuno_discover", "intuno_call_agent", "intuno_send_message"]


def test_get_a2a_tools_shape():
    """A2A tools should include preview and import."""
    tools = get_a2a_tools()
    names = [t["function"]["name"] for t in tools]
    assert names == ["intuno_preview_a2a_card", "intuno_import_a2a_agent"]


@pytest.mark.asyncio
async def test_execute_network_tool_handles_a2a_preview():
    """execute_network_tool should route intuno_preview_a2a_card to preview_a2a_card."""
    mock_client = MagicMock()
    mock_client.preview_a2a_card = AsyncMock(return_value={"name": "External", "skills": []})

    result = await execute_network_tool(
        mock_client,
        tool_name="intuno_preview_a2a_card",
        args={"url": "https://example.com"},
        agent_name="me",
    )

    mock_client.preview_a2a_card.assert_called_once_with(url="https://example.com")
    assert result == {"card": {"name": "External", "skills": []}}


@pytest.mark.asyncio
async def test_execute_network_tool_handles_a2a_import():
    """execute_network_tool should route intuno_import_a2a_agent to import_a2a_agent."""
    fake_agent = MagicMock(agent_id="agent:imported:1", name="Imported", description="desc")
    mock_client = MagicMock()
    mock_client.import_a2a_agent = AsyncMock(return_value=fake_agent)

    result = await execute_network_tool(
        mock_client,
        tool_name="intuno_import_a2a_agent",
        args={"url": "https://example.com"},
        agent_name="me",
    )

    assert result["success"] is True
    assert result["agent_id"] == "agent:imported:1"
