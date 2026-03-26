"""Pydantic models for the Intuno SDK."""

from enum import Enum
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
    agent_id: Optional[str] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Workflow / Execution models
# ---------------------------------------------------------------------------


class WorkflowStepDef(BaseModel):
    """A single step in a workflow definition."""

    model_config = ConfigDict(extra="allow")

    id: str
    type: Optional[str] = None  # agent | skill | condition | sub_workflow | plan
    agent: Optional[str] = None
    skill: Optional[str] = None
    workflow: Optional[str] = None
    goal: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    depends_on: List[str] = []
    parallel_with: Optional[str] = None
    when: Optional[List[Dict[str, Any]]] = None


class WorkflowDef(BaseModel):
    """Workflow definition payload for create_workflow()."""

    model_config = ConfigDict(extra="allow")

    name: str
    steps: List[WorkflowStepDef]
    max_duration_seconds: Optional[int] = None
    max_concurrent_executions: Optional[int] = None
    recovery: Optional[Dict[str, Any]] = None


class WorkflowResponse(BaseModel):
    """Response model for a workflow definition."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    version: int
    owner_id: Optional[str] = None
    definition: Dict[str, Any]
    triggers: Optional[List[Dict[str, Any]]] = None
    recovery: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExecutionStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    timed_out = "timed_out"


class ProcessEntry(BaseModel):
    """A single row in the execution process table."""

    model_config = ConfigDict(extra="ignore")

    id: str
    execution_id: str
    step_id: str
    type: str
    target_id: Optional[str] = None
    target_name: str
    status: str
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempt: int = 1
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    cost: Optional[float] = None


class ExecutionResponse(BaseModel):
    """Response model for a workflow execution."""

    model_config = ConfigDict(extra="ignore")

    id: str
    workflow_id: str
    status: str
    trigger_data: Optional[Dict[str, Any]] = None
    context_id: str
    parent_execution_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
