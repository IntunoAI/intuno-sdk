"""
This module provides integration with the OpenAI API.

It allows converting Intuno Agent Capabilities into a format that can be used
with the OpenAI API's 'tools' parameter.
"""

from typing import Any, Dict, List

from src.intuno_sdk.models import Agent


def get_discovery_tool_openai_schema() -> Dict[str, Any]:
    """
    Returns the OpenAI tool schema for the Intuno agent discovery tool.

    This provides a static definition for a tool that allows an LLM to search
    the Intuno Network. The developer is responsible for handling the actual
    tool call by taking the arguments and passing them to `client.discover()`.

    Returns:
        A dictionary defining the discovery tool in the format expected
        by the OpenAI API.
    """
    return {
        "type": "function",
        "function": {
            "name": "intuno_agent_discovery",
            "description": "Searches the Intuno Agent Network to find agents with specific capabilities. Use this when you need a new tool to solve a user's request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A natural language description of the desired capability to search for.",
                    }
                },
                "required": ["query"],
            },
        },
    }


def make_openai_tools_from_agent(agent: Agent) -> List[Dict[str, Any]]:
    """
    Converts an agent's capabilities into a list of OpenAI-compatible tools.

    This function iterates through the capabilities of a discovered Intuno Agent
    and formats each one into the JSON schema dictionary that the OpenAI API
    expects for its `tools` parameter.

    This allows an OpenAI-powered model to "know" about the Intuno agent's
    capabilities and request to call them. The actual invocation would then
    be handled by your code, using the `agent.invoke()` method.

    Args:
        agent: The discovered Agent object.

    Returns:
        A list of dictionaries, where each dictionary defines a tool in the
        format expected by the OpenAI API.

    Example:
        >>> client = IntunoClient(api_key="...")
        >>> agents = client.discover(query="weather forecaster")
        >>> if agents:
        ...     openai_tools = make_openai_tools_from_agent(agents[0])
        ...
        ...     # Now use this list with an OpenAI client call
        ...     # response = openai_client.chat.completions.create(
        ...     #     model="gpt-4-turbo",
        ...     #     messages=[{"role": "user", "content": "What's the weather in London?"}],
        ...     #     tools=openai_tools,
        ...     # )
    """
    tools: List[Dict[str, Any]] = []
    for capability in agent.capabilities:
        tool_definition = {
            "type": "function",
            "function": {
                "name": capability.display_name,
                "description": capability.description or capability.display_name,
                "parameters": capability.input_schema,
            },
        }
        tools.append(tool_definition)

    return tools
