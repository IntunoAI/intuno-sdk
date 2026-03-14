"""
This module provides integration with the OpenAI API.

It allows converting Intuno Agents into a format that can be used
with the OpenAI API's 'tools' parameter.
"""

from typing import Any, Dict, List

from intuno_sdk.models import Agent, agent_id_to_tool_name


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
    Converts an agent into an OpenAI-compatible tool definition.

    This function formats a discovered Intuno Agent into the JSON schema
    dictionary that the OpenAI API expects for its `tools` parameter.

    Args:
        agent: The discovered Agent object.

    Returns:
        A list with a single dictionary defining the agent as a tool in the
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
    parameters = agent.input_schema or {"type": "object", "properties": {}}
    tool_definition = {
        "type": "function",
        "function": {
            "name": agent_id_to_tool_name(agent.agent_id),
            "description": agent.description,
            "parameters": parameters,
        },
    }
    return [tool_definition]
