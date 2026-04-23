"""
This module provides integration with the LangChain ecosystem.

It allows converting Intuno Agents into LangChain Tools, which can be
used by LangChain agents. It also provides a pre-packaged tool for discovering
agents on the Intuno Network.
"""

from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, Field, create_model

from intuno_sdk.client import AsyncIntunoClient, IntunoClient
from intuno_sdk.models import Agent, agent_id_to_tool_name

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
            summary += f"ID: {agent.agent_id}\n"
            summary += f"Description: {agent.description}\n"
            if agent.input_schema and agent.input_schema.get("properties"):
                props = ", ".join(agent.input_schema["properties"].keys())
                summary += f"Accepts: {props}\n"
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


def create_task_tool(client: Union[IntunoClient, AsyncIntunoClient]) -> BaseTool:
    """
    Creates a LangChain Tool for delegating tasks to the Intuno orchestrator.

    This tool allows an LLM agent to delegate a goal to the Intuno network.
    The orchestrator automatically discovers the best agent and executes it,
    so the LLM only needs to describe the goal in natural language.

    Args:
        client: An initialized synchronous or asynchronous IntunoClient.

    Returns:
        A LangChain Tool that can be used by an agent.

    Example:
        >>> from intuno_sdk.integrations.langchain import create_task_tool
        >>> tool = create_task_tool(client)
        >>> result = tool.invoke({"goal": "Get the weather in Mexico City"})
    """

    class TaskInput(BaseModel):
        goal: str = Field(
            description="A natural language description of what needs to be accomplished."
        )

    def _run_sync(goal: str) -> str:
        if not isinstance(client, IntunoClient):
            raise TypeError("A synchronous IntunoClient is required.")
        task = client.create_task(goal=goal)
        if task.status == "completed" and task.result:
            return str(task.result)
        if task.status == "failed":
            return f"Task failed: {task.error_message}"
        return f"Task status: {task.status}"

    async def _arun_async(goal: str) -> str:
        if not isinstance(client, AsyncIntunoClient):
            raise TypeError("An asynchronous AsyncIntunoClient is required.")
        task = await client.create_task(goal=goal)
        if task.status == "completed" and task.result:
            return str(task.result)
        if task.status == "failed":
            return f"Task failed: {task.error_message}"
        return f"Task status: {task.status}"

    return Tool(
        name="intuno_create_task",
        description=(
            "Delegates a task to the Intuno agent network. "
            "Intuno will automatically find the best specialized agent "
            "and execute it. Use this when you need real-time data, "
            "web search, external services, calculations, or any "
            "specialized capability you don't have natively."
        ),
        func=_run_sync,
        coroutine=_arun_async,
        args_schema=TaskInput,
    )


_JSON_TYPE_MAP: Dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _create_pydantic_model_from_schema(
    schema: Dict[str, Any], model_name: str
) -> Type[BaseModel]:
    """Dynamically creates a Pydantic model from a JSON schema."""
    required_fields = set(schema.get("required", []))
    fields: Dict[str, Any] = {}
    for prop_name, prop_details in schema.get("properties", {}).items():
        field_type: type = _JSON_TYPE_MAP.get(prop_details.get("type", "string"), str)
        description = prop_details.get("description")
        is_required = prop_name in required_fields
        default_value = prop_details.get("default", ... if is_required else None)

        if not is_required and default_value is not ...:
            field_type = Optional[field_type]  # type: ignore[assignment]

        if description:
            fields[prop_name] = (field_type, Field(default=default_value, description=description))
        else:
            fields[prop_name] = (field_type, default_value)

    return create_model(model_name, **fields)


def make_tools_from_agent(agent: Agent) -> List[Tool]:
    """
    Converts an agent into a LangChain Tool.

    Args:
        agent: The discovered Agent object.

    Returns:
        A list with a single LangChain Tool for the agent.
    """
    schema = agent.input_schema or {}
    tool_name = agent_id_to_tool_name(agent.agent_id)
    args_schema = _create_pydantic_model_from_schema(
        schema=schema,
        model_name=f"{tool_name.capitalize()}Input",
    )

    def _run_agent(**kwargs):
        result = agent.invoke(input_data=kwargs)
        if result.success:
            return result.data
        return f"Error during invocation: {result.error}"

    async def _arun_agent(**kwargs):
        result = await agent.ainvoke(input_data=kwargs)
        if result.success:
            return result.data
        return f"Error during invocation: {result.error}"

    tool = Tool(
        name=tool_name,
        description=agent.description,
        func=_run_agent,
        coroutine=_arun_agent,
        args_schema=args_schema,
    )
    return [tool]


# ---------------------------------------------------------------------------
# Network tools — multi-directional comms for LangChain agents
# ---------------------------------------------------------------------------


def create_network_tools(
    client: Union[IntunoClient, AsyncIntunoClient],
    agent_name: str,
    callback_base_url: Optional[str] = None,
) -> List[BaseTool]:
    """Create LangChain tools for participating in the Intuno network.

    Returns three tools:
      - ``intuno_call_agent``: synchronous request/response to another agent
      - ``intuno_send_message``: fire-and-forget async message
      - ``intuno_import_a2a_agent``: import any A2A-compatible external agent

    Each tool auto-provisions a private mesh network between the caller
    (identified by ``agent_name``) and the target, so the LLM doesn't need
    to handle network/participant plumbing.

    Args:
        client: Sync or async IntunoClient.
        agent_name: The LangChain agent's name — used as caller identity.
        callback_base_url: Optional base URL for inbound callbacks (e.g.,
            ``http://localhost:8001``). Required if the agent wants to
            *receive* messages, not just send.
    """

    class CallInput(BaseModel):
        agent_name: str = Field(description="Name of the target agent (from intuno_agent_discovery results).")
        message: str = Field(description="Message to send to the target agent.")

    class SendInput(BaseModel):
        agent_name: str = Field(description="Name of the target agent.")
        message: str = Field(description="Message to send (fire-and-forget).")

    class ImportInput(BaseModel):
        url: str = Field(description="Base URL of the external A2A agent.")

    def _resolve_target_sync(target_name: str) -> Optional[str]:
        if not isinstance(client, IntunoClient):
            raise TypeError("A synchronous IntunoClient is required.")
        agents = client.discover(target_name, limit=5)
        for a in agents:
            if a.name == target_name:
                return a.id
        return None

    async def _resolve_target_async(target_name: str) -> Optional[str]:
        if not isinstance(client, AsyncIntunoClient):
            raise TypeError("An asynchronous AsyncIntunoClient is required.")
        agents = await client.discover(target_name, limit=5)
        for a in agents:
            if a.name == target_name:
                return a.id
        return None

    # ── intuno_call_agent ──
    def _call_sync(agent_name: str, message: str) -> str:  # noqa: ARG001 (shadowing ok)
        target_id = _resolve_target_sync(agent_name)
        if not target_id:
            return f"Agent '{agent_name}' not found on the network."
        network_id, my_pid, target_pid = client.ensure_network(
            caller_name=_outer_agent_name,
            target_name=agent_name,
            caller_type="agent",
            target_agent_id=target_id,
            callback_base_url=callback_base_url,
        )
        result = client.network_call(network_id, my_pid, target_pid, message)
        return str(result.response)

    async def _call_async(agent_name: str, message: str) -> str:
        target_id = await _resolve_target_async(agent_name)
        if not target_id:
            return f"Agent '{agent_name}' not found on the network."
        network_id, my_pid, target_pid = await client.ensure_network(
            caller_name=_outer_agent_name,
            target_name=agent_name,
            caller_type="agent",
            target_agent_id=target_id,
            callback_base_url=callback_base_url,
        )
        result = await client.network_call(network_id, my_pid, target_pid, message)
        return str(result.response)

    # ── intuno_send_message ──
    def _send_sync(agent_name: str, message: str) -> str:
        target_id = _resolve_target_sync(agent_name)
        if not target_id:
            return f"Agent '{agent_name}' not found on the network."
        network_id, my_pid, target_pid = client.ensure_network(
            caller_name=_outer_agent_name,
            target_name=agent_name,
            caller_type="agent",
            target_agent_id=target_id,
            callback_base_url=callback_base_url,
        )
        msg = client.network_send(network_id, my_pid, target_pid, message)
        return f"Message sent (id={msg.id}, status={msg.status})."

    async def _send_async(agent_name: str, message: str) -> str:
        target_id = await _resolve_target_async(agent_name)
        if not target_id:
            return f"Agent '{agent_name}' not found on the network."
        network_id, my_pid, target_pid = await client.ensure_network(
            caller_name=_outer_agent_name,
            target_name=agent_name,
            caller_type="agent",
            target_agent_id=target_id,
            callback_base_url=callback_base_url,
        )
        msg = await client.network_send(network_id, my_pid, target_pid, message)
        return f"Message sent (id={msg.id}, status={msg.status})."

    # ── intuno_import_a2a_agent ──
    def _import_sync(url: str) -> str:
        if not isinstance(client, IntunoClient):
            raise TypeError("A synchronous IntunoClient is required.")
        agent = client.import_a2a_agent(url=url)
        return f"Imported: {agent.name} ({agent.agent_id}). Now discoverable on the network."

    async def _import_async(url: str) -> str:
        if not isinstance(client, AsyncIntunoClient):
            raise TypeError("An asynchronous AsyncIntunoClient is required.")
        agent = await client.import_a2a_agent(url=url)
        return f"Imported: {agent.name} ({agent.agent_id}). Now discoverable on the network."

    _outer_agent_name = agent_name

    return [
        Tool(
            name="intuno_call_agent",
            description=(
                "Send a message to another agent on the Intuno network and wait for its reply "
                "(synchronous call). Auto-provisions a private network between you and the target. "
                "Use when you need the target's response before continuing."
            ),
            func=_call_sync,
            coroutine=_call_async,
            args_schema=CallInput,
        ),
        Tool(
            name="intuno_send_message",
            description=(
                "Send an asynchronous message to another agent on the Intuno network (fire-and-forget). "
                "The message is delivered without blocking. Use for notifications or when you don't need a reply."
            ),
            func=_send_sync,
            coroutine=_send_async,
            args_schema=SendInput,
        ),
        Tool(
            name="intuno_import_a2a_agent",
            description=(
                "Import an external A2A-compatible agent into the Intuno network by its URL. "
                "Once imported, the agent shows up in discovery and can be invoked or called like any other agent."
            ),
            func=_import_sync,
            coroutine=_import_async,
            args_schema=ImportInput,
        ),
    ]
