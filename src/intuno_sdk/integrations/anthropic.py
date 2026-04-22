"""
Anthropic (Claude) integration for the Intuno SDK.

Provides tool schemas in the format expected by the Anthropic Messages API,
network communication tools, and a utility for converting OpenAI-format
tool definitions to Anthropic format.
"""

from __future__ import annotations

from typing import Any, Dict, List

from intuno_sdk.models import Agent, agent_id_to_tool_name

from intuno_sdk.integrations.openai import execute_network_tool  # noqa: F401


def openai_tool_to_anthropic(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an OpenAI-format tool definition to Anthropic format."""
    fn = tool["function"]
    return {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
    }


def get_discovery_tool_anthropic_schema() -> Dict[str, Any]:
    """Returns the Anthropic tool schema for Intuno agent discovery."""
    return {
        "name": "intuno_agent_discovery",
        "description": (
            "Searches the Intuno Agent Network to find agents with specific "
            "capabilities. Use this when you need a new tool to solve a "
            "user's request."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A natural language description of the desired capability to search for.",
                }
            },
            "required": ["query"],
        },
    }


def get_task_tool_anthropic_schema() -> Dict[str, Any]:
    """Returns the Anthropic tool schema for the Intuno create_task orchestrator."""
    return {
        "name": "intuno_create_task",
        "description": (
            "Delegates a task to the Intuno agent network. "
            "Intuno will automatically find the best specialized agent "
            "and execute it. Use this when you need real-time data, "
            "web search, external services, calculations, or any "
            "specialized capability you don't have natively."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "A natural language description of what needs to be accomplished.",
                }
            },
            "required": ["goal"],
        },
    }


def make_anthropic_tools_from_agent(agent: Agent) -> List[Dict[str, Any]]:
    """Converts an Intuno Agent into an Anthropic-compatible tool definition."""
    return [
        {
            "name": agent_id_to_tool_name(agent.agent_id),
            "description": agent.description,
            "input_schema": agent.input_schema or {"type": "object", "properties": {}},
        }
    ]


def get_network_tools() -> List[Dict[str, Any]]:
    """Return Anthropic tool definitions for Intuno network communication.

    These tools let a Claude model autonomously discover agents and
    communicate with them through the Intuno network.
    """
    return [
        {
            "name": "intuno_discover",
            "description": (
                "Search the Intuno network for agents by describing what you need "
                "in natural language. Uses semantic search — describe the capability, "
                "not the agent name. Returns matching agents with similarity scores."
            ),
            "input_schema": {
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
        {
            "name": "intuno_call_agent",
            "description": (
                "Send a message to another agent on the Intuno network and get their "
                "response immediately (synchronous call). Automatically creates a "
                "network connection if needed. Use this to collaborate with other agents."
            ),
            "input_schema": {
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
        {
            "name": "intuno_send_message",
            "description": (
                "Send an asynchronous message to another agent on the Intuno network. "
                "The message is delivered but you don't wait for a response. "
                "Use this for fire-and-forget communication."
            ),
            "input_schema": {
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
    ]
