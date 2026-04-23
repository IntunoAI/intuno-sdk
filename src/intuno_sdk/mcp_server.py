"""
Intuno MCP Server
~~~~~~~~~~~~~~~~~

An MCP (Model Context Protocol) server that exposes the Intuno Agent Network
as tools and resources for AI assistants.

Usage:
    INTUNO_API_KEY=your-key python -m intuno_sdk.mcp_server
    INTUNO_API_KEY=your-key intuno-mcp
    INTUNO_API_KEY=your-key intuno-mcp --transport streamable-http
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from intuno_sdk.client import AsyncIntunoClient
from intuno_sdk.constants import DEFAULT_BASE_URL
from intuno_sdk.exceptions import IntunoError

mcp = FastMCP(
    "Intuno Agent Network",
    instructions=(
        "Discover, invoke, and orchestrate AI agents on the Intuno Agent Network. "
        "Use these tools to find agents by description, execute agent functions, "
        "and run multi-step tasks."
    ),
)

_client: Optional[AsyncIntunoClient] = None


def _get_client() -> AsyncIntunoClient:
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("INTUNO_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "INTUNO_API_KEY environment variable is required. "
            "Set it before starting the MCP server."
        )

    base_url = os.environ.get("INTUNO_BASE_URL", DEFAULT_BASE_URL)
    _client = AsyncIntunoClient(api_key=api_key, base_url=base_url)
    return _client


def _agent_summary(agent: Any) -> Dict[str, Any]:
    """Compact JSON-serializable summary of an Agent for tool responses."""
    summary: Dict[str, Any] = {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "description": agent.description,
        "auth_type": agent.auth_type,
        "endpoint": agent.endpoint,
    }
    if agent.input_schema:
        summary["input_schema"] = agent.input_schema
    if agent.tags:
        summary["tags"] = agent.tags
    if agent.category:
        summary["category"] = agent.category
    if agent.similarity_score is not None:
        summary["similarity_score"] = agent.similarity_score
    return summary


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def discover_agents(query: str, limit: int = 5) -> str:
    """Search for AI agents by describing what you need in natural language.

    Returns a list of matching agents with their metadata.
    Use this to find agents before invoking them.

    Args:
        query: Natural language description of the desired agent
               (e.g. "summarize text", "translate to Spanish", "analyze sentiment").
        limit: Maximum number of agents to return (1-50, default 5).
    """
    client = _get_client()
    try:
        agents = await client.discover(query, limit=min(max(limit, 1), 50))
        results = [_agent_summary(a) for a in agents]
        return json.dumps(results, indent=2)
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_agent_details(agent_id: str) -> str:
    """Get full details of a specific agent including its input schema.

    Use this after discovering agents to inspect a particular agent's
    input/output schemas before invoking it.

    Args:
        agent_id: The agent ID (e.g. "agent:namespace:name:version").
    """
    client = _get_client()
    try:
        agent = await client.get_agent(agent_id)
        return json.dumps(_agent_summary(agent), indent=2)
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def invoke_agent(
    agent_id: str,
    input_data: dict,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> str:
    """Invoke an agent with the provided input data.

    Before calling this, use discover_agents or get_agent_details to find
    the correct agent_id and its input_schema.

    Args:
        agent_id: The agent ID to invoke.
        input_data: Input data matching the agent's input_schema.
        conversation_id: Optional conversation ID to link this invocation to.
        message_id: Optional message ID within the conversation.
    """
    client = _get_client()
    try:
        result = await client.ainvoke(
            agent_id=agent_id,
            input_data=input_data,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        return json.dumps(
            {
                "success": result.success,
                "data": result.data,
                "latency_ms": result.latency_ms,
            },
            indent=2,
        )
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def create_task(
    goal: str,
    input_data: Optional[dict] = None,
    async_mode: bool = False,
    idempotency_key: Optional[str] = None,
) -> str:
    """Create and run a multi-step task via the Intuno orchestrator.

    The orchestrator will automatically discover relevant agents, plan the
    execution steps, and invoke them in sequence to achieve the goal.

    Args:
        goal: Natural language description of what you want to accomplish.
        input_data: Optional input data for the task.
        async_mode: If true, the task runs in background; use get_task_status to poll.
        idempotency_key: Optional key to prevent duplicate task creation.
    """
    client = _get_client()
    try:
        result = await client.create_task(
            goal=goal,
            input_data=input_data,
            async_mode=async_mode,
            idempotency_key=idempotency_key,
        )
        return json.dumps(
            {
                "task_id": result.id,
                "status": result.status,
                "goal": result.goal,
                "result": result.result,
                "error_message": result.error_message,
                "steps": result.steps,
            },
            indent=2,
        )
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def list_conversations(limit: int = 50) -> str:
    """List conversations for the current user.

    Use this to browse chat history before reading messages from a specific conversation.

    Args:
        limit: Maximum number of conversations to return (default 50).
    """
    client = _get_client()
    try:
        conversations = await client.list_conversations()
        results = [
            {
                "id": c.id,
                "title": c.title,
                "external_user_id": c.external_user_id,
                "created_at": c.created_at,
            }
            for c in conversations[:limit]
        ]
        return json.dumps(results, indent=2)
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_conversation_messages(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """List messages in a conversation.

    Use this to read the chat history of a conversation.
    Call list_conversations first to get conversation IDs.

    Args:
        conversation_id: The conversation ID.
        limit: Maximum number of messages to return (1-500, default 100).
        offset: Offset for pagination (default 0).
    """
    client = _get_client()
    try:
        messages = await client.get_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
        )
        results = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at,
            }
            for m in messages
        ]
        return json.dumps(results, indent=2)
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_task_status(task_id: str) -> str:
    """Check the current status and result of a previously created task.

    Use this to poll async tasks or to retrieve the final result of a completed task.

    Args:
        task_id: The task ID returned by create_task.
    """
    client = _get_client()
    try:
        result = await client.get_task(task_id)
        return json.dumps(
            {
                "task_id": result.id,
                "status": result.status,
                "goal": result.goal,
                "result": result.result,
                "error_message": result.error_message,
                "steps": result.steps,
                "created_at": result.created_at,
                "updated_at": result.updated_at,
            },
            indent=2,
        )
    except IntunoError as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Network tools (multi-directional communication)
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_network(name: str, topology: str = "mesh") -> str:
    """Create a new communication network for multi-directional agent comms.

    Use this to set up a space where multiple agents can exchange calls,
    messages, and mailbox entries. Default topology "mesh" lets every
    participant talk to every other participant.

    Args:
        name: Human-readable network name.
        topology: One of "mesh", "star", "ring", "custom" (default "mesh").
    """
    client = _get_client()
    try:
        net = await client.create_network(name=name, topology=topology)
        return json.dumps(
            {"network_id": net.id, "name": net.name, "topology": net.topology_type},
            indent=2,
        )
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def join_network(
    network_id: str,
    name: str,
    participant_type: str = "agent",
    callback_url: Optional[str] = None,
    polling_enabled: bool = False,
) -> str:
    """Add a participant to an existing network.

    Participants can be agents (receive pushed calls/messages via callback_url)
    or personas (poll for messages). Enable polling_enabled=true when the
    participant has no public callback URL.

    Args:
        network_id: ID from create_network.
        name: Unique name of the participant within the network.
        participant_type: "agent" | "persona" | "orchestrator".
        callback_url: Where Intuno POSTs inbound calls/messages for this participant.
        polling_enabled: If true, skip push delivery; read via get_inbox.
    """
    client = _get_client()
    try:
        p = await client.join_network(
            network_id=network_id,
            name=name,
            participant_type=participant_type,
            callback_url=callback_url,
            polling_enabled=polling_enabled,
        )
        return json.dumps(
            {"participant_id": p.id, "network_id": p.network_id, "name": p.name},
            indent=2,
        )
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def send_network_message(
    network_id: str,
    sender_participant_id: str,
    recipient_participant_id: str,
    content: str,
) -> str:
    """Send an asynchronous message from one participant to another within a network.

    Fire-and-forget — the message is delivered and stored without blocking.
    For a synchronous request/response, use call_network_participant instead.

    Args:
        network_id: The network.
        sender_participant_id: Sending participant.
        recipient_participant_id: Receiving participant.
        content: Message body.
    """
    client = _get_client()
    try:
        msg = await client.network_send(
            network_id=network_id,
            sender_participant_id=sender_participant_id,
            recipient_participant_id=recipient_participant_id,
            content=content,
        )
        return json.dumps(
            {"message_id": msg.id, "status": msg.status, "channel_type": msg.channel_type},
            indent=2,
        )
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_network_context(network_id: str, limit: int = 50) -> str:
    """Read the shared context (recent messages) of a network.

    Use this to catch up on a network's conversation history — useful for
    late-joining participants or summarization.

    Args:
        network_id: The network to read.
        limit: Max number of entries to return (1-200, default 50).
    """
    client = _get_client()
    try:
        ctx = await client.get_network_context(network_id=network_id, limit=limit)
        entries = [
            {
                "sender": e.sender,
                "recipient": e.recipient,
                "channel": e.channel,
                "content": e.content,
                "timestamp": e.timestamp,
            }
            for e in ctx.entries
        ]
        return json.dumps({"network_id": ctx.network_id, "entries": entries}, indent=2)
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def import_a2a_agent(url: str) -> str:
    """Import an external A2A-compatible agent into the Intuno network.

    Fetches the Agent Card from the given URL, registers it, and indexes
    it for semantic discovery. Once imported, the agent is indistinguishable
    from natively registered agents — it shows up in discover_agents results
    and can be invoked the same way.

    Args:
        url: Base URL of the external A2A agent (e.g., "https://some-agent.com").
    """
    client = _get_client()
    try:
        agent = await client.import_a2a_agent(url=url)
        return json.dumps(_agent_summary(agent), indent=2)
    except IntunoError as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("intuno://agents/trending")
async def trending_agents() -> str:
    """List of currently trending agents on the Intuno network, ordered by recent invocation count."""
    client = _get_client()
    try:
        agents = await client.list_trending_agents(window_days=7, limit=20)
        return json.dumps([_agent_summary(a) for a in agents], indent=2)
    except IntunoError as e:
        return json.dumps({"error": str(e)})


@mcp.resource("intuno://agents/new")
async def new_agents() -> str:
    """Recently published agents on the Intuno network (last 7 days)."""
    client = _get_client()
    try:
        agents = await client.list_new_agents(days=7, limit=20)
        return json.dumps([_agent_summary(a) for a in agents], indent=2)
    except IntunoError as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Intuno MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for HTTP-based transports (default: 8080)",
    )
    args = parser.parse_args()

    if not os.environ.get("INTUNO_API_KEY"):
        print(
            "Error: INTUNO_API_KEY environment variable is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, port=args.port)


if __name__ == "__main__":
    main()
