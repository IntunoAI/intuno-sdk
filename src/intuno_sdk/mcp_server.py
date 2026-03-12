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
        "Use these tools to find agents by capability, execute agent functions, "
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
    caps = []
    for c in agent.capabilities:
        cap_info: Dict[str, Any] = {"id": c.id}
        if c.name:
            cap_info["name"] = c.name
        if c.description:
            cap_info["description"] = c.description
        if c.input_schema:
            cap_info["input_schema"] = c.input_schema
        if c.output_schema:
            cap_info["output_schema"] = c.output_schema
        caps.append(cap_info)

    summary: Dict[str, Any] = {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "description": agent.description,
        "version": agent.version,
        "capabilities": caps,
    }
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

    Returns a list of matching agents with their capabilities and metadata.
    Use this to find agents before invoking them.

    Args:
        query: Natural language description of the desired capability
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
    """Get full details of a specific agent including all its capabilities and schemas.

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
    capability_id: str,
    input_data: dict,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> str:
    """Invoke a specific capability of an agent with the provided input data.

    Before calling this, use discover_agents or get_agent_details to find
    the correct agent_id, capability_id, and required input schema.

    Args:
        agent_id: The agent ID to invoke.
        capability_id: The capability ID to execute.
        input_data: Input data matching the capability's input_schema.
        conversation_id: Optional conversation ID to link this invocation to.
        message_id: Optional message ID within the conversation.
    """
    client = _get_client()
    try:
        result = await client.ainvoke(
            agent_id=agent_id,
            capability_id=capability_id,
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
