"""Pydantic models for the Intuno SDK."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, PrivateAttr

if TYPE_CHECKING:
    from src.intuno_sdk.client import AsyncIntunoClient, IntunoClient


class Capability(BaseModel):
    """Represents an agent's capability."""

    id: str
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(..., alias="inputSchema")
    output_schema: Dict[str, Any] = Field(..., alias="outputSchema")


class Agent(BaseModel):
    """Represents an Intuno Agent."""

    id: str  # Internal UUID
    agent_id: str = Field(..., alias="agentId")
    name: str
    description: str
    version: str
    tags: List[str]
    is_active: bool = Field(..., alias="isActive")
    capabilities: List[Capability]

    _client: Optional[Union["IntunoClient", "AsyncIntunoClient"]] = PrivateAttr(
        default=None
    )

    def _find_capability_id(self, name_or_id: str) -> str:
        """Finds a capability ID from a name or ID."""
        # Check if it's a direct ID match first
        for cap in self.capabilities:
            if cap.id == name_or_id:
                return cap.id

        # If not, check for a name match
        for cap in self.capabilities:
            if cap.name == name_or_id:
                return cap.id

        raise ValueError(
            f"Could not find a capability with name or ID '{name_or_id}' on agent '{self.name}'"
        )

    def invoke(
        self, capability_name_or_id: str, input_data: Dict[str, Any]
    ) -> "InvokeResult":
        """
        Synchronously invoke one of this agent's capabilities.

        Args:
            capability_name_or_id: The name or ID of the capability to use.
            input_data: A dictionary containing the input for the capability.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        if not self._client or not hasattr(self._client, "invoke"):
            raise RuntimeError(
                "A synchronous client is required for this operation. Use 'ainvoke' for async clients."
            )

        capability_id = self._find_capability_id(capability_name_or_id)
        return self._client.invoke(
            agent_id=self.id, capability_id=capability_id, input_data=input_data
        )

    async def ainvoke(
        self, capability_name_or_id: str, input_data: Dict[str, Any]
    ) -> "InvokeResult":
        """
        Asynchronously invoke one of this agent's capabilities.

        Args:
            capability_name_or_id: The name or ID of the capability to use.
            input_data: A dictionary containing the input for the capability.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        if not self._client or not hasattr(self._client, "ainvoke"):
            raise RuntimeError(
                "An asynchronous client is required for this operation. Use 'invoke' for sync clients."
            )

        capability_id = self._find_capability_id(capability_name_or_id)
        return await self._client.ainvoke(
            agent_id=self.id, capability_id=capability_id, input_data=input_data
        )


class InvokeResult(BaseModel):
    """Represents the result of an agent invocation."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: int = Field(..., alias="latencyMs")
    status_code: int = Field(..., alias="statusCode")
