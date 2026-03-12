"""
This module provides integration with the LangChain ecosystem.

It allows converting Intuno Agent Capabilities into LangChain Tools, which can be
used by LangChain agents. It also provides a pre-packaged tool for discovering
agents on the Intuno Network.
"""

from typing import Any, Dict, List, Type, Union

from pydantic import BaseModel, Field, create_model

from src.intuno_sdk.client import AsyncIntunoClient, IntunoClient
from src.intuno_sdk.models import Agent

try:
    from langchain_core.tools import BaseTool, Tool
except ImportError:
    raise ImportError(
        "LangChain is not installed. Please install it with 'pip install intuno-sdk[langchain]'"
    )


def create_discovery_tool(client: Union[IntunoClient, AsyncIntunoClient]) -> BaseTool:
    """
    Creates a LangChain Tool for discovering agents on the Intuno Network.

    This tool allows an LLM agent to search for other agents by describing
    the capability it needs in natural language.

    Args:
        client: An initialized synchronous or asynchronous IntunoClient.

    Returns:
        A LangChain Tool that can be used by an agent.
    """

    class DiscoveryInput(BaseModel):
        query: str = Field(
            description="A natural language description of the desired capability to search for."
        )

    def _format_discovery_result(agents: List[Agent]) -> str:
        if not agents:
            return "No agents found matching the query."

        summary = f"Found {len(agents)} agent(s):\n"
        for i, agent in enumerate(agents):
            summary += f"\n--- Agent {i + 1} ---\n"
            summary += f"Name: {agent.name}\n"
            summary += f"ID: {agent.id}\n"
            summary += f"Description: {agent.description}\n"
            summary += "Capabilities:\n"
            for cap in agent.capabilities:
                summary += f"  - {cap.display_name}: {cap.description or 'No description'}\n"
        return summary

    def _run_sync(query: str) -> str:
        if not isinstance(client, IntunoClient):
            raise TypeError("A synchronous IntunoClient is required.")
        agents = client.discover(query=query)
        return _format_discovery_result(agents)

    async def _arun_async(query: str) -> str:
        if not isinstance(client, AsyncIntunoClient):
            raise TypeError("An asynchronous AsyncIntunoClient is required.")
        agents = await client.discover(query=query)
        return _format_discovery_result(agents)

    return Tool(
        name="intuno_agent_discovery",
        description="Searches the Intuno Agent Network to find agents with specific capabilities. Use this when you need a new tool to solve a user's request.",
        func=_run_sync,
        coroutine=_arun_async,
        args_schema=DiscoveryInput,
    )


def _create_pydantic_model_from_schema(
    schema: Dict[str, Any], model_name: str
) -> Type[BaseModel]:
    """Dynamically creates a Pydantic model from a JSON schema."""
    fields: Dict[str, Any] = {}
    for prop_name, prop_details in schema.get("properties", {}).items():
        field_type = str  # Default to string
        if prop_details.get("type") == "integer":
            field_type = int
        elif prop_details.get("type") == "number":
            field_type = float
        elif prop_details.get("type") == "boolean":
            field_type = bool

        default_value = prop_details.get("default", ...)
        fields[prop_name] = (field_type, default_value)

    return create_model(model_name, **fields)


def make_tools_from_agent(agent: Agent) -> List[Tool]:
    """
    Converts an agent's capabilities into a list of LangChain Tools.

    This function iterates through the capabilities of a discovered Intuno Agent
    and wraps each one in a LangChain `Tool` object.

    Args:
        agent: The discovered Agent object.

    Returns:
        A list of LangChain Tool objects, one for each capability.
    """
    tools: List[Tool] = []
    for capability in agent.capabilities:
        cap_name = capability.display_name
        args_schema = _create_pydantic_model_from_schema(
            schema=capability.input_schema,
            model_name=f"{cap_name.capitalize()}Input",
        )

        def _run_capability(_cap_name=cap_name, **kwargs):
            result = agent.invoke(
                capability_name_or_id=_cap_name, input_data=kwargs
            )
            if result.success:
                return result.data
            return f"Error during invocation: {result.error}"

        async def _arun_capability(_cap_name=cap_name, **kwargs):
            result = await agent.ainvoke(
                capability_name_or_id=_cap_name, input_data=kwargs
            )
            if result.success:
                return result.data
            return f"Error during invocation: {result.error}"

        tool = Tool(
            name=cap_name,
            description=capability.description or cap_name,
            func=_run_capability,
            coroutine=_arun_capability,
            args_schema=args_schema,
        )
        tools.append(tool)

    return tools
