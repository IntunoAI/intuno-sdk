"""Pydantic models for the Intuno SDK."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union


def agent_id_to_tool_name(agent_id: str) -> str:
    """Convert an agent_id to a valid tool name (replaces - and : with _)."""
    return agent_id.replace("-", "_").replace(":", "_")

from pydantic import BaseModel, ConfigDict, PrivateAttr

if TYPE_CHECKING:
    from intuno_sdk.client import AsyncIntunoClient, IntunoClient


class Agent(BaseModel):
    """Represents an Intuno Agent."""

    model_config = ConfigDict(extra="ignore")

    id: str
    agent_id: str
    name: str
    description: str
    tags: List[str] = []
    is_active: bool = True
    auth_type: str = "public"
    endpoint: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    similarity_score: Optional[float] = None
    created_at: Optional[str] = None

    _client: Optional[Union["IntunoClient", "AsyncIntunoClient"]] = PrivateAttr(
        default=None
    )

    def invoke(self, input_data: Dict[str, Any]) -> "InvokeResult":
        """
        Synchronously invoke this agent.

        Args:
            input_data: A dictionary containing the input for the agent.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        if not self._client or not hasattr(self._client, "invoke"):
            raise RuntimeError(
                "A synchronous client is required for this operation. Use 'ainvoke' for async clients."
            )

        return self._client.invoke(agent_id=self.agent_id, input_data=input_data)

    async def ainvoke(self, input_data: Dict[str, Any]) -> "InvokeResult":
        """
        Asynchronously invoke this agent.

        Args:
            input_data: A dictionary containing the input for the agent.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        if not self._client or not hasattr(self._client, "ainvoke"):
            raise RuntimeError(
                "An asynchronous client is required for this operation. Use 'invoke' for sync clients."
            )

        return await self._client.ainvoke(agent_id=self.agent_id, input_data=input_data)


class InvokeResult(BaseModel):
    """Represents the result of an agent invocation."""

    model_config = ConfigDict(extra="allow")

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: int = 0
    status_code: int = 0
    conversation_id: Optional[str] = None


class TaskResult(BaseModel):
    """Represents the result of a task execution."""

    model_config = ConfigDict(extra="ignore")

    id: str
    status: str
    goal: str
    input: Dict[str, Any] = {}
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[str] = None
    external_user_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Conversation(BaseModel):
    """Represents a chat conversation."""

    model_config = ConfigDict(extra="ignore")

    id: str
    integration_id: Optional[str] = None
    external_user_id: Optional[str] = None
    title: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Message(BaseModel):
    """Represents a message in a conversation."""

    model_config = ConfigDict(extra="ignore")

    id: str
    conversation_id: str
    role: str  # user | assistant | system | tool
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
