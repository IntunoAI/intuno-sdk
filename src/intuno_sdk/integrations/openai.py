"""
This module provides integration with the OpenAI API.

It allows converting Intuno Agents into a format that can be used
with the OpenAI API's 'tools' parameter, including network communication
tools that let LLMs autonomously discover and talk to other agents.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List

from intuno_sdk.models import Agent, agent_id_to_tool_name

if TYPE_CHECKING:
    from intuno_sdk.client import AsyncIntunoClient


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


def get_task_tool_openai_schema() -> Dict[str, Any]:
    """
    Returns the OpenAI tool schema for the Intuno create_task orchestrator.

    This provides a static definition for a tool that delegates a task to the
    Intuno agent network. The orchestrator automatically discovers the best
    agent and executes it, so the LLM only needs to describe the goal in
    natural language.

    The developer is responsible for handling the actual tool call by taking
    the ``goal`` argument and passing it to ``client.create_task(goal=...)``.

    Returns:
        A dictionary defining the task tool in the format expected
        by the OpenAI API.

    Example:
        >>> from intuno_sdk.integrations.openai import get_task_tool_openai_schema
        >>> tool = get_task_tool_openai_schema()
        >>> # Pass to any OpenAI-compatible API
        >>> response = openai_client.chat.completions.create(
        ...     model="gpt-4",
        ...     messages=[{"role": "user", "content": "What's the weather?"}],
        ...     tools=[tool],
        ... )
    """
    return {
        "type": "function",
        "function": {
            "name": "intuno_create_task",
            "description": (
                "Delegates a task to the Intuno agent network. "
                "Intuno will automatically find the best specialized agent "
                "and execute it. Use this when you need real-time data, "
                "web search, external services, calculations, or any "
                "specialized capability you don't have natively."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "A natural language description of what needs to be accomplished.",
                    }
                },
                "required": ["goal"],
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


# ---------------------------------------------------------------------------
# Network tools — LLM-ready tools for multi-directional communication
# ---------------------------------------------------------------------------


def get_network_tools() -> List[Dict[str, Any]]:
    """Return OpenAI tool definitions for Intuno network communication.

    These tools let an LLM autonomously discover agents and communicate
    with them through the Intuno network. Pass these to OpenAI's
    chat.completions.create() along with your own tools.

    Example:
        >>> from intuno_sdk.integrations.openai import get_network_tools, execute_network_tool
        >>> tools = get_network_tools()
        >>> response = openai.chat.completions.create(
        ...     model="gpt-4o",
        ...     messages=messages,
        ...     tools=tools,
        ... )
        >>> for tc in response.choices[0].message.tool_calls:
        ...     result = await execute_network_tool(client, tc.function.name, json.loads(tc.function.arguments), "my-agent")
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "intuno_discover",
                "description": (
                    "Search the Intuno network for agents by describing what you need "
                    "in natural language. Uses semantic search — describe the capability, "
                    "not the agent name. Returns matching agents with similarity scores."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language description of the capability you need (e.g., 'translate text to Spanish', 'summarize long documents')",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "intuno_call_agent",
                "description": (
                    "Send a message to another agent on the Intuno network and get their "
                    "response immediately (synchronous call). Automatically creates a "
                    "network connection if needed. Use this to collaborate with other agents."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "Name of the agent to call (from discover results)",
                        },
                        "message": {
                            "type": "string",
                            "description": "The message to send to the agent",
                        },
                    },
                    "required": ["agent_name", "message"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "intuno_send_message",
                "description": (
                    "Send an asynchronous message to another agent on the Intuno network. "
                    "The message is delivered but you don't wait for a response. "
                    "Use this for fire-and-forget communication."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "Name of the agent to message",
                        },
                        "message": {
                            "type": "string",
                            "description": "The message to send",
                        },
                    },
                    "required": ["agent_name", "message"],
                },
            },
        },
    ]


def get_a2a_tools() -> List[Dict[str, Any]]:
    """Return OpenAI tool definitions for A2A agent import.

    Lets an LLM import any A2A-compatible external agent into the Intuno
    network at runtime. Once imported, the agent is discoverable and
    invocable like any native agent. Pair with ``execute_network_tool``
    to handle the tool calls.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "intuno_preview_a2a_card",
                "description": (
                    "Preview an external A2A agent's Agent Card without importing it. "
                    "Use this to inspect the agent's capabilities, skills, and endpoints "
                    "before deciding to import."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Base URL of the A2A-compatible agent.",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "intuno_import_a2a_agent",
                "description": (
                    "Import an external A2A-compatible agent into the Intuno network. "
                    "The agent is registered, indexed for semantic discovery, and becomes "
                    "invocable like any native agent."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Base URL of the A2A-compatible agent.",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
    ]


async def execute_network_tool(
    client: "AsyncIntunoClient",
    tool_name: str,
    args: Dict[str, Any],
    agent_name: str,
    callback_base_url: str | None = None,
) -> Dict[str, Any]:
    """Execute an Intuno network tool call from an LLM.

    This is the companion to get_network_tools(). When the LLM calls one
    of the network tools, pass the tool name and arguments here to execute it.

    Args:
        client: An AsyncIntunoClient instance.
        tool_name: The function name from the tool call.
        args: The parsed arguments from the tool call.
        agent_name: Your agent's name (used for network provisioning).
        callback_base_url: Base URL for agent callbacks (e.g., "http://localhost:8001").

    Returns:
        A dictionary with the tool result, suitable for passing back to the LLM.
    """
    if tool_name == "intuno_discover":
        query = args.get("query", "")
        agents = await client.discover(query, limit=10)
        return {
            "found": len(agents),
            "agents": [
                {
                    "name": a.name,
                    "description": a.description[:200],
                    "tags": a.tags,
                    "similarity_score": a.similarity_score,
                    "category": a.category,
                }
                for a in agents
            ],
        }

    if tool_name == "intuno_call_agent":
        target_name = args["agent_name"]
        message = args["message"]

        # Find target agent in registry
        agents = await client.discover(target_name, limit=5)
        target_reg_id = None
        for a in agents:
            if a.name == target_name:
                target_reg_id = a.id
                break

        if not target_reg_id:
            # Fallback: try exact search
            try:
                agents_list = await client._http_client.get(
                    "/registry/agents", params={"search": target_name, "limit": 5}
                )
                for a in agents_list.json():
                    if a.get("name") == target_name:
                        target_reg_id = a["id"]
                        break
            except Exception:
                pass

        if not target_reg_id:
            return {"error": f"Agent '{target_name}' not found on the network"}

        # Ensure network and call
        network_id, my_pid, target_pid = await client.ensure_network(
            caller_name=agent_name,
            target_name=target_name,
            caller_type="agent",
            target_agent_id=target_reg_id,
            callback_base_url=callback_base_url,
        )

        result = await client.network_call(
            network_id=network_id,
            sender_participant_id=my_pid,
            recipient_participant_id=target_pid,
            content=message,
        )

        response = result.response
        if isinstance(response, dict):
            response = response.get("response", response.get("content", str(response)))

        return {
            "success": result.success,
            "agent": target_name,
            "response": str(response),
        }

    if tool_name == "intuno_preview_a2a_card":
        card = await client.preview_a2a_card(url=args["url"])
        return {"card": card}

    if tool_name == "intuno_import_a2a_agent":
        try:
            agent = await client.import_a2a_agent(url=args["url"])
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {
            "success": True,
            "agent_id": agent.agent_id,
            "name": agent.name,
            "description": agent.description[:200] if agent.description else "",
        }

    if tool_name == "intuno_send_message":
        target_name = args["agent_name"]
        message = args["message"]

        # Find and ensure network (same pattern)
        agents = await client.discover(target_name, limit=5)
        target_reg_id = None
        for a in agents:
            if a.name == target_name:
                target_reg_id = a.id
                break

        if not target_reg_id:
            return {"error": f"Agent '{target_name}' not found on the network"}

        network_id, my_pid, target_pid = await client.ensure_network(
            caller_name=agent_name,
            target_name=target_name,
            caller_type="agent",
            target_agent_id=target_reg_id,
            callback_base_url=callback_base_url,
        )

        msg = await client.network_send(
            network_id=network_id,
            sender_participant_id=my_pid,
            recipient_participant_id=target_pid,
            content=message,
        )

        return {"success": True, "message_id": msg.id, "status": msg.status}

    return {"error": f"Unknown tool: {tool_name}"}
