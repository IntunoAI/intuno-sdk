"""Tests for the Intuno SDK integrations."""

from unittest.mock import MagicMock

import pytest

from intuno_sdk.integrations.langchain import (
    create_discovery_tool,
    create_task_tool,
    make_tools_from_agent,
)
from intuno_sdk.integrations.openai import (
    get_discovery_tool_openai_schema,
    get_task_tool_openai_schema,
    make_openai_tools_from_agent,
)
from intuno_sdk.models import Agent, Capability

# --- Fixtures ---


@pytest.fixture
def mock_agent():
    """Returns a mock Agent object for testing."""
    cap = Capability(
        id="cap-id-1",
        name="test_capability",
        description="A test capability",
        input_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
        output_schema={},
    )
    agent = Agent(
        id="uuid-1",
        agent_id="agent-1",
        name="Test Agent",
        description="A test agent",
        version="1.0",
        tags=["test"],
        is_active=True,
        capabilities=[cap],
    )
    # Mock the invoke method for testing the tool's function
    agent.invoke = MagicMock(return_value={"success": True, "data": "mocked result"})
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

    tool = create_task_tool(mock_client)
    assert tool.name == "intuno_create_task"
    assert "Delegates a task" in tool.description

    result = tool.func(goal="Get the weather in CDMX")
    mock_client.create_task.assert_called_once_with(goal="Get the weather in CDMX")
    assert "21°C" in result


def test_create_discovery_tool():
    """Test the creation of the LangChain discovery tool."""
    mock_client = MagicMock()
    mock_client.discover.return_value = []  # Mock the discover method

    tool = create_discovery_tool(mock_client)
    assert tool.name == "intuno_agent_discovery"
    assert "Searches the Intuno Agent Network" in tool.description

    # Test the tool's execution
    tool.func(query="test query")
    mock_client.discover.assert_called_once_with(query="test query")


def test_make_tools_from_agent(mock_agent: Agent):
    """Test converting an agent's capabilities to LangChain tools."""
    tools = make_tools_from_agent(mock_agent)

    assert len(tools) == 1
    tool = tools[0]

    assert tool.name == "test_capability"
    assert tool.description == "A test capability"
    assert tool.args_schema is not None

    # Test the generated tool's function
    tool.func(x=5)
    mock_agent.invoke.assert_called_once_with(
        capability_name_or_id="test_capability",
        input_data={"x": 5},
    )


# --- OpenAI Integration Tests ---


def test_get_task_tool_openai_schema():
    """Test the generation of the OpenAI create_task tool schema."""
    schema = get_task_tool_openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "intuno_create_task"
    assert "goal" in schema["function"]["parameters"]["properties"]
    assert "goal" in schema["function"]["parameters"]["required"]
    assert "Delegates a task" in schema["function"]["description"]


def test_get_discovery_tool_openai_schema():
    """Test the generation of the OpenAI discovery tool schema."""
    schema = get_discovery_tool_openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "intuno_agent_discovery"
    assert "query" in schema["function"]["parameters"]["properties"]


def test_make_openai_tools_from_agent(mock_agent: Agent):
    """Test converting an agent's capabilities to OpenAI tool schemas."""
    tools = make_openai_tools_from_agent(mock_agent)

    assert len(tools) == 1
    tool = tools[0]

    assert tool["type"] == "function"
    function_def = tool["function"]

    assert function_def["name"] == "test_capability"
    assert function_def["description"] == "A test capability"
    assert "x" in function_def["parameters"]["properties"]
