from typing import Any, Dict, List, Optional, Union
from uuid import UUID as UUIDType

import httpx
from pydantic import ValidationError

from intuno_sdk.constants import DEFAULT_BASE_URL, SDK_VERSION
from intuno_sdk.exceptions import (
    APIKeyMissingError,
    AuthenticationError,
    InvocationError,
    IntunoError,
)
from intuno_sdk.models import (
    Agent,
    CallResult,
    ContextEntry,
    Conversation,
    ExecutionResponse,
    InvokeResult,
    Message,
    Network,
    NetworkContext,
    NetworkMessage,
    NetworkParticipant,
    ProcessEntry,
    TaskResult,
    WorkflowDef,
    WorkflowResponse,
)


def _build_auth_headers(
    api_key: str,
    act_as_user_id: Optional[Union[str, "UUIDType"]] = None,
) -> dict:
    """Build auth headers.

    - Plain user key / JWT: sends ``X-API-Key`` or ``Authorization: Bearer``.
    - Service delegation (``act_as_user_id`` set): sends ``X-Service-Key``
      + ``X-On-Behalf-Of`` instead. The ``api_key`` argument is the
      service secret in this mode.
    """
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"Intuno-SDK/{SDK_VERSION}",
    }
    if act_as_user_id is not None:
        headers["X-Service-Key"] = api_key
        headers["X-On-Behalf-Of"] = str(act_as_user_id)
        return headers
    # JWT tokens start with 'eyJ' (base64-encoded JSON header)
    if api_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["X-API-Key"] = api_key
    return headers


class IntunoClient:
    """
    The main synchronous client for interacting with the Intuno Agent Network.

    Service delegation
    ------------------
    Pass ``act_as_user_id`` to operate on behalf of a specific user. The
    ``api_key`` you provide is then used as a *service secret* — sent as
    ``X-Service-Key`` alongside ``X-On-Behalf-Of`` — and the backend
    attributes every call to the delegated user. Only internal services
    (wisdom-agents today) should use this mode.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        *,
        act_as_user_id: Optional[Union[str, UUIDType]] = None,
    ):
        if not api_key:
            raise APIKeyMissingError()

        self.api_key = api_key
        self.base_url = base_url
        self.act_as_user_id = act_as_user_id
        self._http_client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=_build_auth_headers(api_key, act_as_user_id=act_as_user_id),
        )

    def discover(self, query: str, limit: int = 10) -> List[Agent]:
        """
        Discover agents using natural language.

        Args:
            query: A natural language description of the desired capability.
            limit: The maximum number of agents to return.

        Returns:
            A list of Agent objects matching the query.
        """
        try:
            response = self._http_client.get(
                "/registry/discover", params={"query": query, "limit": limit}
            )
            response.raise_for_status()
            agents = [Agent(**agent_data) for agent_data in response.json()]
            for agent in agents:
                agent._client = self
            return agents
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def invoke(
        self,
        agent_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
    ) -> InvokeResult:
        """
        Invoke an agent.

        Args:
            agent_id: The ID of the agent to invoke.
            input_data: A dictionary containing the input for the agent.
            conversation_id: Optional conversation ID to attach this invocation to.
            message_id: Optional message ID within the conversation.
            external_user_id: Optional end-user ID for multi-user apps.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "input": input_data,
        }
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        if message_id is not None:
            payload["message_id"] = message_id
        if external_user_id is not None:
            payload["external_user_id"] = external_user_id

        try:
            response = self._http_client.post("/broker/invoke", json=payload)
            response.raise_for_status()
            result = InvokeResult(**response.json())
            if not result.success:
                raise InvocationError(
                    f"Invocation failed: {result.error} (Status: {result.status_code})"
                )
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            try:
                error_details = e.response.json().get("detail", e.response.text)
            except Exception:
                error_details = e.response.text
            raise IntunoError(f"API request failed: {error_details}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def create_task(
        self,
        goal: str,
        input_data: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
        async_mode: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> TaskResult:
        """
        Create and run a multi-step task via the orchestrator.

        Args:
            goal: Natural language goal for the task.
            input_data: Optional input data for the task.
            conversation_id: Optional conversation to attach the task to.
            message_id: Optional message within the conversation.
            external_user_id: Optional end-user ID for multi-user apps.
            async_mode: If True, task runs in background; poll with get_task().
            idempotency_key: Optional key to prevent duplicate task creation.

        Returns:
            A TaskResult with the task state (completed if sync, pending if async).
        """
        payload: Dict[str, Any] = {
            "goal": goal,
            "input": input_data or {},
        }
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        if message_id is not None:
            payload["message_id"] = message_id
        if external_user_id is not None:
            payload["external_user_id"] = external_user_id

        headers = {}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key

        try:
            response = self._http_client.post(
                "/tasks",
                json=payload,
                params={"async": str(async_mode).lower()},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            if response.status_code == 202:
                return TaskResult(
                    id=data["task_id"],
                    status="pending",
                    goal=goal,
                    input=input_data or {},
                )
            return TaskResult(**data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            try:
                error_details = e.response.json().get("detail", e.response.text)
            except Exception:
                error_details = e.response.text
            raise IntunoError(f"Task creation failed: {error_details}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_task(self, task_id: str) -> TaskResult:
        """
        Get the current state of a task.

        Args:
            task_id: The task ID to poll.

        Returns:
            A TaskResult with the current task state.
        """
        try:
            response = self._http_client.get(f"/tasks/{task_id}")
            response.raise_for_status()
            return TaskResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            try:
                error_details = e.response.json().get("detail", e.response.text)
            except Exception:
                error_details = e.response.text
            raise IntunoError(f"Failed to get task: {error_details}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_agent(self, agent_id: str) -> Agent:
        """
        Get full agent details by agent_id.

        Args:
            agent_id: The agent ID (e.g. agent:ns:name:version).

        Returns:
            An Agent object with its metadata.
        """
        try:
            response = self._http_client.get(f"/registry/agents/{agent_id}")
            response.raise_for_status()
            agent = Agent(**response.json())
            agent._client = self
            return agent
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Agent '{agent_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def list_new_agents(self, days: int = 7, limit: int = 20) -> List[Agent]:
        """
        List recently published agents.

        Args:
            days: Agents created in the last N days.
            limit: Maximum number of agents to return.

        Returns:
            A list of Agent objects.
        """
        try:
            response = self._http_client.get(
                "/registry/agents/new", params={"days": days, "limit": limit}
            )
            response.raise_for_status()
            agents = [Agent(**agent_data) for agent_data in response.json()]
            for agent in agents:
                agent._client = self
            return agents
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def list_trending_agents(self, window_days: int = 7, limit: int = 20) -> List[Agent]:
        """
        List trending agents by invocation count.

        Args:
            window_days: Invocation count window in days.
            limit: Maximum number of agents to return.

        Returns:
            A list of Agent objects ordered by popularity.
        """
        try:
            response = self._http_client.get(
                "/registry/agents/trending",
                params={"window_days": window_days, "limit": limit},
            )
            response.raise_for_status()
            agents = [Agent(**agent_data) for agent_data in response.json()]
            for agent in agents:
                agent._client = self
            return agents
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def list_conversations(
        self,
        integration_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
    ) -> List[Conversation]:
        """
        List conversations for the current user.

        Args:
            integration_id: Optional filter by integration ID.
            external_user_id: Optional filter by external user ID.

        Returns:
            A list of Conversation objects.
        """
        params: Dict[str, str] = {}
        if integration_id is not None:
            params["integration_id"] = integration_id
        if external_user_id is not None:
            params["external_user_id"] = external_user_id
        try:
            response = self._http_client.get(
                "/conversations", params=params if params else None
            )
            response.raise_for_status()
            data = response.json()
            return [Conversation(**self._norm_conv(c)) for c in data]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError("Conversations not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_conversation(self, conversation_id: str) -> Conversation:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The conversation ID.

        Returns:
            A Conversation object.
        """
        try:
            response = self._http_client.get(f"/conversations/{conversation_id}")
            response.raise_for_status()
            return Conversation(**self._norm_conv(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Conversation '{conversation_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_messages(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """
        List messages in a conversation.

        Args:
            conversation_id: The conversation ID.
            limit: Maximum number of messages (1-500, default 100).
            offset: Offset for pagination (default 0).

        Returns:
            A list of Message objects.
        """
        try:
            response = self._http_client.get(
                f"/conversations/{conversation_id}/messages",
                params={"limit": limit, "offset": offset},
            )
            response.raise_for_status()
            data = response.json()
            return [Message(**self._norm_msg(m)) for m in data]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Conversation '{conversation_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_message(self, conversation_id: str, message_id: str) -> Message:
        """
        Get a specific message by ID.

        Args:
            conversation_id: The conversation ID.
            message_id: The message ID.

        Returns:
            A Message object.
        """
        try:
            response = self._http_client.get(
                f"/conversations/{conversation_id}/messages/{message_id}"
            )
            response.raise_for_status()
            return Message(**self._norm_msg(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Message '{message_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── Workflow management ────────────────────────────────────────────────────

    def create_workflow(self, workflow: WorkflowDef) -> WorkflowResponse:
        """Create a new workflow definition."""
        try:
            response = self._http_client.post(
                "/workflows", json=workflow.model_dump(exclude_none=True)
            )
            response.raise_for_status()
            return WorkflowResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_workflow(self, workflow_id: str) -> WorkflowResponse:
        """Get a workflow definition by ID."""
        try:
            response = self._http_client.get(f"/workflows/{workflow_id}")
            response.raise_for_status()
            return WorkflowResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Workflow '{workflow_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def list_workflows(
        self,
        name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowResponse]:
        """List workflow definitions."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if name is not None:
            params["name"] = name
        try:
            response = self._http_client.get("/workflows", params=params)
            response.raise_for_status()
            return [WorkflowResponse(**w) for w in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── Execution management ───────────────────────────────────────────────────

    def run_workflow(
        self, workflow_id: str, trigger_data: Optional[Dict[str, Any]] = None
    ) -> ExecutionResponse:
        """Trigger a workflow execution."""
        try:
            response = self._http_client.post(
                f"/workflows/{workflow_id}/run",
                json={"trigger_data": trigger_data or {}},
            )
            response.raise_for_status()
            return ExecutionResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_execution(self, execution_id: str) -> ExecutionResponse:
        """Get the current state of a workflow execution."""
        try:
            response = self._http_client.get(f"/executions/{execution_id}")
            response.raise_for_status()
            return ExecutionResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Execution '{execution_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def cancel_execution(self, execution_id: str) -> ExecutionResponse:
        """Cancel a running workflow execution."""
        try:
            response = self._http_client.post(f"/executions/{execution_id}/cancel")
            response.raise_for_status()
            return ExecutionResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_process_table(self, execution_id: str) -> List[ProcessEntry]:
        """Get the process table for a workflow execution."""
        try:
            response = self._http_client.get(f"/executions/{execution_id}/ps")
            response.raise_for_status()
            return [ProcessEntry(**e) for e in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── Network Communication ──────────────────────────────────────

    def create_network(
        self,
        name: str,
        topology: str = "mesh",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Network:
        """Create a communication network."""
        try:
            response = self._http_client.post(
                "/networks",
                json={"name": name, "topology_type": topology, "metadata": metadata or {}},
            )
            response.raise_for_status()
            return Network(**self._norm_network(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Failed to create network: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def list_networks(self, limit: int = 50) -> List[Network]:
        """List networks owned by the current user."""
        try:
            response = self._http_client.get("/networks", params={"limit": limit})
            response.raise_for_status()
            return [Network(**self._norm_network(n)) for n in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_network(self, network_id: str) -> Network:
        """Get a network by ID."""
        try:
            response = self._http_client.get(f"/networks/{network_id}")
            response.raise_for_status()
            return Network(**self._norm_network(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Network '{network_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def delete_network(self, network_id: str) -> None:
        """Delete a network. Only the owner can delete."""
        try:
            response = self._http_client.delete(f"/networks/{network_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Network '{network_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except httpx.RequestError as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def join_network(
        self,
        network_id: str,
        name: str,
        participant_type: str = "agent",
        agent_id: Optional[str] = None,
        callback_url: Optional[str] = None,
        polling_enabled: bool = False,
    ) -> NetworkParticipant:
        """Join a network as a participant."""
        body: Dict[str, Any] = {
            "participant_type": participant_type,
            "name": name,
            "polling_enabled": polling_enabled,
        }
        if agent_id:
            body["agent_id"] = agent_id
        if callback_url:
            body["callback_url"] = callback_url
        try:
            response = self._http_client.post(
                f"/networks/{network_id}/participants", json=body
            )
            response.raise_for_status()
            return NetworkParticipant(**self._norm_participant(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Failed to join network: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def list_participants(self, network_id: str) -> List[NetworkParticipant]:
        """List participants in a network."""
        try:
            response = self._http_client.get(f"/networks/{network_id}/participants")
            response.raise_for_status()
            return [NetworkParticipant(**self._norm_participant(p)) for p in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def leave_network(self, network_id: str, participant_id: str) -> None:
        """Remove a participant from a network."""
        try:
            response = self._http_client.delete(
                f"/networks/{network_id}/participants/{participant_id}"
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Participant '{participant_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except httpx.RequestError as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def network_call(
        self,
        network_id: str,
        sender_participant_id: str,
        recipient_participant_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CallResult:
        """Make a synchronous call to another participant (blocks until response)."""
        body: Dict[str, Any] = {
            "sender_participant_id": sender_participant_id,
            "recipient_participant_id": recipient_participant_id,
            "content": content,
        }
        if metadata:
            body["metadata"] = metadata
        try:
            response = self._http_client.post(
                f"/networks/{network_id}/call", json=body
            )
            response.raise_for_status()
            return CallResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Network call failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def network_send(
        self,
        network_id: str,
        sender_participant_id: str,
        recipient_participant_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NetworkMessage:
        """Send an async message to another participant."""
        body: Dict[str, Any] = {
            "sender_participant_id": sender_participant_id,
            "recipient_participant_id": recipient_participant_id,
            "content": content,
        }
        if metadata:
            body["metadata"] = metadata
        try:
            response = self._http_client.post(
                f"/networks/{network_id}/messages/send", json=body
            )
            response.raise_for_status()
            return NetworkMessage(**self._norm_net_msg(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Send failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def network_messages(
        self,
        network_id: str,
        limit: int = 50,
        channel_type: Optional[str] = None,
    ) -> List[NetworkMessage]:
        """List messages in a network."""
        params: Dict[str, Any] = {"limit": limit}
        if channel_type:
            params["channel_type"] = channel_type
        try:
            response = self._http_client.get(
                f"/networks/{network_id}/messages", params=params
            )
            response.raise_for_status()
            return [NetworkMessage(**self._norm_net_msg(m)) for m in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def send_to_mailbox(
        self,
        network_id: str,
        sender_participant_id: str,
        recipient_participant_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NetworkMessage:
        """Send a mailbox message (stored without push delivery; recipient polls via get_inbox)."""
        body: Dict[str, Any] = {
            "sender_participant_id": sender_participant_id,
            "recipient_participant_id": recipient_participant_id,
            "content": content,
        }
        if metadata:
            body["metadata"] = metadata
        try:
            response = self._http_client.post(
                f"/networks/{network_id}/mailbox", json=body
            )
            response.raise_for_status()
            return NetworkMessage(**self._norm_net_msg(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Mailbox send failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_inbox(
        self,
        network_id: str,
        participant_id: str,
        channel_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[NetworkMessage]:
        """Poll inbox for a participant. Returns unread messages only."""
        params: Dict[str, Any] = {"limit": limit}
        if channel_type:
            params["channel_type"] = channel_type
        try:
            response = self._http_client.get(
                f"/networks/{network_id}/inbox/{participant_id}", params=params
            )
            response.raise_for_status()
            return [NetworkMessage(**self._norm_net_msg(m)) for m in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def acknowledge_messages(
        self, network_id: str, message_ids: List[str]
    ) -> int:
        """Mark messages as read. Returns the number actually acknowledged."""
        try:
            response = self._http_client.post(
                f"/networks/{network_id}/messages/ack",
                json={"message_ids": message_ids},
            )
            response.raise_for_status()
            return int(response.json().get("acknowledged", 0))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Ack failed: {e.response.text}") from e
        except httpx.RequestError as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def get_network_context(
        self, network_id: str, limit: int = 50
    ) -> NetworkContext:
        """Read the shared context of a network (recent messages, ordered)."""
        try:
            response = self._http_client.get(
                f"/networks/{network_id}/context", params={"limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            entries = [ContextEntry(**self._norm_context_entry(e)) for e in data.get("entries", [])]
            return NetworkContext(network_id=str(data.get("network_id", network_id)), entries=entries)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def ensure_network(
        self,
        caller_name: str,
        target_name: str,
        caller_type: str = "agent",
        target_agent_id: Optional[str] = None,
        callback_base_url: Optional[str] = None,
    ) -> tuple:
        """Get or create a private network between two participants.

        Returns (network_id, caller_participant_id, target_participant_id).
        """
        network_name = f"private-{caller_name}-{target_name}"
        networks = self.list_networks(limit=200)

        for net in networks:
            if net.name == network_name and net.status == "active":
                participants = self.list_participants(net.id)
                caller_pid = None
                target_pid = None
                for p in participants:
                    if p.name == caller_name and p.status == "active":
                        caller_pid = p.id
                    elif p.name == target_name and p.status == "active":
                        target_pid = p.id
                if caller_pid and target_pid:
                    return net.id, caller_pid, target_pid

        net = self.create_network(
            name=network_name,
            metadata={"purpose": f"Channel: {caller_name} <-> {target_name}", "auto_created": True},
        )

        caller_kwargs: Dict[str, Any] = {"participant_type": caller_type}
        if caller_type == "agent" and callback_base_url:
            caller_kwargs["callback_url"] = f"{callback_base_url}/agents/{caller_name}/callback"
        elif caller_type == "persona":
            caller_kwargs["polling_enabled"] = True
        caller_p = self.join_network(net.id, caller_name, **caller_kwargs)

        target_kwargs: Dict[str, Any] = {"participant_type": "agent"}
        if target_agent_id:
            target_kwargs["agent_id"] = target_agent_id
        if callback_base_url:
            target_kwargs["callback_url"] = f"{callback_base_url}/agents/{target_name}/callback"
        target_p = self.join_network(net.id, target_name, **target_kwargs)

        return net.id, caller_p.id, target_p.id

    # ── A2A agent import ─────────────────────────────────────────────

    def preview_a2a_card(self, url: str) -> Dict[str, Any]:
        """Fetch an A2A Agent Card from a URL without importing it."""
        try:
            response = self._http_client.get(
                "/a2a/agents/fetch-card", params={"url": url}
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                raise IntunoError(data.get("error", "Failed to fetch Agent Card"))
            return data.get("card", {})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Failed to fetch card: {e.response.text}") from e
        except httpx.RequestError as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def import_a2a_agent(self, url: str) -> Agent:
        """Import an external A2A agent by URL.

        Fetches the Agent Card, registers the agent, and indexes it for
        semantic discovery. The returned ``Agent`` is fully discoverable
        via ``discover()`` and invocable via ``invoke()``.
        """
        try:
            response = self._http_client.post(
                "/a2a/agents/import", json={"url": url}
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                raise IntunoError(data.get("error", "Import failed"))
            return self.get_agent(data["agent_id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"A2A import failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    def refresh_a2a_agent(self, agent_id: str) -> Agent:
        """Re-fetch an imported A2A agent's card and update its registry entry."""
        try:
            response = self._http_client.post(f"/a2a/agents/{agent_id}/refresh")
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                raise IntunoError(data.get("error", "Refresh failed"))
            return self.get_agent(data["agent_id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Agent '{agent_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── Network normalizers ──────────────────────────────────────────

    @staticmethod
    def _norm_network(obj: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(obj)
        for k in ("id", "owner_id"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        for k in ("created_at", "updated_at"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        return out

    @staticmethod
    def _norm_participant(obj: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(obj)
        for k in ("id", "network_id", "agent_id"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        for k in ("created_at", "updated_at"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        return out

    @staticmethod
    def _norm_net_msg(obj: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(obj)
        for k in ("id", "network_id", "sender_participant_id", "recipient_participant_id", "in_reply_to_id"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        for k in ("created_at", "updated_at"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        return out

    @staticmethod
    def _norm_context_entry(obj: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(obj)
        if "message_id" in out and out["message_id"] is not None:
            out["message_id"] = str(out["message_id"])
        if "timestamp" in out and out["timestamp"] is not None:
            out["timestamp"] = str(out["timestamp"])
        return out

    @staticmethod
    def _norm_conv(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize conversation dict for Conversation model (UUID/datetime to str)."""
        out: Dict[str, Any] = dict(obj)
        for k in ("id", "user_id", "integration_id"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        for k in ("created_at", "updated_at"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        return out

    @staticmethod
    def _norm_msg(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize message dict for Message model (UUID/datetime to str)."""
        out: Dict[str, Any] = dict(obj)
        for k in ("id", "conversation_id"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        if "created_at" in out and out["created_at"] is not None:
            out["created_at"] = str(out["created_at"])
        return out

    def close(self):
        """Closes the underlying HTTP client."""
        self._http_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncIntunoClient:
    """
    The main asynchronous client for interacting with the Intuno Agent Network.

    Service delegation: see ``IntunoClient`` — same ``act_as_user_id`` kwarg.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        *,
        act_as_user_id: Optional[Union[str, UUIDType]] = None,
    ):
        if not api_key:
            raise APIKeyMissingError()

        self.api_key = api_key
        self.base_url = base_url
        self.act_as_user_id = act_as_user_id
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=_build_auth_headers(api_key, act_as_user_id=act_as_user_id),
        )

    async def discover(self, query: str, limit: int = 10) -> List[Agent]:
        """
        Discover agents using natural language.

        Args:
            query: A natural language description of the desired capability.
            limit: The maximum number of agents to return.

        Returns:
            A list of Agent objects matching the query.
        """
        try:
            response = await self._http_client.get(
                "/registry/discover", params={"query": query, "limit": limit}
            )
            response.raise_for_status()
            agents = [Agent(**agent_data) for agent_data in response.json()]
            for agent in agents:
                agent._client = self
            return agents
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def ainvoke(
        self,
        agent_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
    ) -> InvokeResult:
        """
        Asynchronously invoke an agent.

        Args:
            agent_id: The ID of the agent to invoke.
            input_data: A dictionary containing the input for the agent.
            conversation_id: Optional conversation ID to attach this invocation to.
            message_id: Optional message ID within the conversation.
            external_user_id: Optional end-user ID for multi-user apps.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "input": input_data,
        }
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        if message_id is not None:
            payload["message_id"] = message_id
        if external_user_id is not None:
            payload["external_user_id"] = external_user_id

        try:
            response = await self._http_client.post("/broker/invoke", json=payload)
            response.raise_for_status()
            result = InvokeResult(**response.json())
            if not result.success:
                raise InvocationError(
                    f"Invocation failed: {result.error} (Status: {result.status_code})"
                )
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            try:
                error_details = e.response.json().get("detail", e.response.text)
            except Exception:
                error_details = e.response.text
            raise IntunoError(f"API request failed: {error_details}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def create_task(
        self,
        goal: str,
        input_data: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
        async_mode: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> TaskResult:
        """
        Create and run a multi-step task via the orchestrator.

        Args:
            goal: Natural language goal for the task.
            input_data: Optional input data for the task.
            conversation_id: Optional conversation to attach the task to.
            message_id: Optional message within the conversation.
            external_user_id: Optional end-user ID for multi-user apps.
            async_mode: If True, task runs in background; poll with get_task().
            idempotency_key: Optional key to prevent duplicate task creation.

        Returns:
            A TaskResult with the task state (completed if sync, pending if async).
        """
        payload: Dict[str, Any] = {
            "goal": goal,
            "input": input_data or {},
        }
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        if message_id is not None:
            payload["message_id"] = message_id
        if external_user_id is not None:
            payload["external_user_id"] = external_user_id

        headers = {}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key

        try:
            response = await self._http_client.post(
                "/tasks",
                json=payload,
                params={"async": str(async_mode).lower()},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            if response.status_code == 202:
                return TaskResult(
                    id=data["task_id"],
                    status="pending",
                    goal=goal,
                    input=input_data or {},
                )
            return TaskResult(**data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            try:
                error_details = e.response.json().get("detail", e.response.text)
            except Exception:
                error_details = e.response.text
            raise IntunoError(f"Task creation failed: {error_details}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_task(self, task_id: str) -> TaskResult:
        """
        Get the current state of a task.

        Args:
            task_id: The task ID to poll.

        Returns:
            A TaskResult with the current task state.
        """
        try:
            response = await self._http_client.get(f"/tasks/{task_id}")
            response.raise_for_status()
            return TaskResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            try:
                error_details = e.response.json().get("detail", e.response.text)
            except Exception:
                error_details = e.response.text
            raise IntunoError(f"Failed to get task: {error_details}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_agent(self, agent_id: str) -> Agent:
        """
        Get full agent details by agent_id.

        Args:
            agent_id: The agent ID (e.g. agent:ns:name:version).

        Returns:
            An Agent object with its metadata.
        """
        try:
            response = await self._http_client.get(f"/registry/agents/{agent_id}")
            response.raise_for_status()
            agent = Agent(**response.json())
            agent._client = self
            return agent
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Agent '{agent_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def list_conversations(
        self,
        integration_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
    ) -> List[Conversation]:
        """
        List conversations for the current user.

        Args:
            integration_id: Optional filter by integration ID.
            external_user_id: Optional filter by external user ID.

        Returns:
            A list of Conversation objects.
        """
        params: Dict[str, str] = {}
        if integration_id is not None:
            params["integration_id"] = integration_id
        if external_user_id is not None:
            params["external_user_id"] = external_user_id
        try:
            response = await self._http_client.get(
                "/conversations", params=params if params else None
            )
            response.raise_for_status()
            data = response.json()
            return [Conversation(**IntunoClient._norm_conv(c)) for c in data]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError("Conversations not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_conversation(self, conversation_id: str) -> Conversation:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The conversation ID.

        Returns:
            A Conversation object.
        """
        try:
            response = await self._http_client.get(f"/conversations/{conversation_id}")
            response.raise_for_status()
            return Conversation(**IntunoClient._norm_conv(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Conversation '{conversation_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_messages(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """
        List messages in a conversation.

        Args:
            conversation_id: The conversation ID.
            limit: Maximum number of messages (1-500, default 100).
            offset: Offset for pagination (default 0).

        Returns:
            A list of Message objects.
        """
        try:
            response = await self._http_client.get(
                f"/conversations/{conversation_id}/messages",
                params={"limit": limit, "offset": offset},
            )
            response.raise_for_status()
            data = response.json()
            return [Message(**IntunoClient._norm_msg(m)) for m in data]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Conversation '{conversation_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_message(self, conversation_id: str, message_id: str) -> Message:
        """
        Get a specific message by ID.

        Args:
            conversation_id: The conversation ID.
            message_id: The message ID.

        Returns:
            A Message object.
        """
        try:
            response = await self._http_client.get(
                f"/conversations/{conversation_id}/messages/{message_id}"
            )
            response.raise_for_status()
            return Message(**IntunoClient._norm_msg(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Message '{message_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def list_new_agents(self, days: int = 7, limit: int = 20) -> List[Agent]:
        """
        List recently published agents.

        Args:
            days: Agents created in the last N days.
            limit: Maximum number of agents to return.

        Returns:
            A list of Agent objects.
        """
        try:
            response = await self._http_client.get(
                "/registry/agents/new", params={"days": days, "limit": limit}
            )
            response.raise_for_status()
            agents = [Agent(**agent_data) for agent_data in response.json()]
            for agent in agents:
                agent._client = self
            return agents
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def list_trending_agents(self, window_days: int = 7, limit: int = 20) -> List[Agent]:
        """
        List trending agents by invocation count.

        Args:
            window_days: Invocation count window in days.
            limit: Maximum number of agents to return.

        Returns:
            A list of Agent objects ordered by popularity.
        """
        try:
            response = await self._http_client.get(
                "/registry/agents/trending",
                params={"window_days": window_days, "limit": limit},
            )
            response.raise_for_status()
            agents = [Agent(**agent_data) for agent_data in response.json()]
            for agent in agents:
                agent._client = self
            return agents
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── Workflow management ────────────────────────────────────────────────────

    async def create_workflow(self, workflow: WorkflowDef) -> WorkflowResponse:
        """Create a new workflow definition."""
        try:
            response = await self._http_client.post(
                "/workflows", json=workflow.model_dump(exclude_none=True)
            )
            response.raise_for_status()
            return WorkflowResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_workflow(self, workflow_id: str) -> WorkflowResponse:
        """Get a workflow definition by ID."""
        try:
            response = await self._http_client.get(f"/workflows/{workflow_id}")
            response.raise_for_status()
            return WorkflowResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Workflow '{workflow_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def list_workflows(
        self,
        name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowResponse]:
        """List workflow definitions."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if name is not None:
            params["name"] = name
        try:
            response = await self._http_client.get("/workflows", params=params)
            response.raise_for_status()
            return [WorkflowResponse(**w) for w in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── Execution management ───────────────────────────────────────────────────

    async def run_workflow(
        self, workflow_id: str, trigger_data: Optional[Dict[str, Any]] = None
    ) -> ExecutionResponse:
        """Trigger a workflow execution."""
        try:
            response = await self._http_client.post(
                f"/workflows/{workflow_id}/run",
                json={"trigger_data": trigger_data or {}},
            )
            response.raise_for_status()
            return ExecutionResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_execution(self, execution_id: str) -> ExecutionResponse:
        """Get the current state of a workflow execution."""
        try:
            response = await self._http_client.get(f"/executions/{execution_id}")
            response.raise_for_status()
            return ExecutionResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Execution '{execution_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def cancel_execution(self, execution_id: str) -> ExecutionResponse:
        """Cancel a running workflow execution."""
        try:
            response = await self._http_client.post(f"/executions/{execution_id}/cancel")
            response.raise_for_status()
            return ExecutionResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_process_table(self, execution_id: str) -> List[ProcessEntry]:
        """Get the process table for a workflow execution."""
        try:
            response = await self._http_client.get(f"/executions/{execution_id}/ps")
            response.raise_for_status()
            return [ProcessEntry(**e) for e in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── Network Communication ──────────────────────────────────────

    async def create_network(
        self,
        name: str,
        topology: str = "mesh",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Network:
        """Create a communication network."""
        try:
            response = await self._http_client.post(
                "/networks",
                json={"name": name, "topology_type": topology, "metadata": metadata or {}},
            )
            response.raise_for_status()
            return Network(**self._norm_network(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Failed to create network: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def list_networks(self, limit: int = 50) -> List[Network]:
        """List networks owned by the current user."""
        try:
            response = await self._http_client.get(
                "/networks", params={"limit": limit}
            )
            response.raise_for_status()
            return [Network(**self._norm_network(n)) for n in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def join_network(
        self,
        network_id: str,
        name: str,
        participant_type: str = "agent",
        agent_id: Optional[str] = None,
        callback_url: Optional[str] = None,
        polling_enabled: bool = False,
    ) -> NetworkParticipant:
        """Join a network as a participant."""
        body: Dict[str, Any] = {
            "participant_type": participant_type,
            "name": name,
            "polling_enabled": polling_enabled,
        }
        if agent_id:
            body["agent_id"] = agent_id
        if callback_url:
            body["callback_url"] = callback_url
        try:
            response = await self._http_client.post(
                f"/networks/{network_id}/participants", json=body
            )
            response.raise_for_status()
            return NetworkParticipant(**self._norm_participant(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Failed to join network: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def list_participants(self, network_id: str) -> List[NetworkParticipant]:
        """List participants in a network."""
        try:
            response = await self._http_client.get(
                f"/networks/{network_id}/participants"
            )
            response.raise_for_status()
            return [NetworkParticipant(**self._norm_participant(p)) for p in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def network_call(
        self,
        network_id: str,
        sender_participant_id: str,
        recipient_participant_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CallResult:
        """Make a synchronous call to another participant (blocks until response)."""
        body: Dict[str, Any] = {
            "sender_participant_id": sender_participant_id,
            "recipient_participant_id": recipient_participant_id,
            "content": content,
        }
        if metadata:
            body["metadata"] = metadata
        try:
            response = await self._http_client.post(
                f"/networks/{network_id}/call", json=body
            )
            response.raise_for_status()
            return CallResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Network call failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def network_send(
        self,
        network_id: str,
        sender_participant_id: str,
        recipient_participant_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NetworkMessage:
        """Send an async message to another participant."""
        body: Dict[str, Any] = {
            "sender_participant_id": sender_participant_id,
            "recipient_participant_id": recipient_participant_id,
            "content": content,
        }
        if metadata:
            body["metadata"] = metadata
        try:
            response = await self._http_client.post(
                f"/networks/{network_id}/messages/send", json=body
            )
            response.raise_for_status()
            return NetworkMessage(**self._norm_net_msg(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Send failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def network_messages(
        self,
        network_id: str,
        limit: int = 50,
        channel_type: Optional[str] = None,
    ) -> List[NetworkMessage]:
        """List messages in a network."""
        params: Dict[str, Any] = {"limit": limit}
        if channel_type:
            params["channel_type"] = channel_type
        try:
            response = await self._http_client.get(
                f"/networks/{network_id}/messages", params=params
            )
            response.raise_for_status()
            return [NetworkMessage(**self._norm_net_msg(m)) for m in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def ensure_network(
        self,
        caller_name: str,
        target_name: str,
        caller_type: str = "agent",
        target_agent_id: Optional[str] = None,
        callback_base_url: Optional[str] = None,
    ) -> tuple:
        """Get or create a private network between two participants.

        Returns (network_id, caller_participant_id, target_participant_id).
        """
        network_name = f"private-{caller_name}-{target_name}"
        networks = await self.list_networks(limit=200)

        for net in networks:
            if net.name == network_name and net.status == "active":
                participants = await self.list_participants(net.id)
                caller_pid = None
                target_pid = None
                for p in participants:
                    if p.name == caller_name and p.status == "active":
                        caller_pid = p.id
                    elif p.name == target_name and p.status == "active":
                        target_pid = p.id
                if caller_pid and target_pid:
                    return net.id, caller_pid, target_pid

        # Create new
        net = await self.create_network(
            name=network_name,
            metadata={"purpose": f"Channel: {caller_name} <-> {target_name}", "auto_created": True},
        )

        # Join caller
        caller_kwargs: Dict[str, Any] = {"participant_type": caller_type}
        if caller_type == "agent" and callback_base_url:
            caller_kwargs["callback_url"] = f"{callback_base_url}/agents/{caller_name}/callback"
        elif caller_type == "persona":
            caller_kwargs["polling_enabled"] = True
        caller_p = await self.join_network(net.id, caller_name, **caller_kwargs)

        # Join target
        target_kwargs: Dict[str, Any] = {"participant_type": "agent"}
        if target_agent_id:
            target_kwargs["agent_id"] = target_agent_id
        if callback_base_url:
            target_kwargs["callback_url"] = f"{callback_base_url}/agents/{target_name}/callback"
        target_p = await self.join_network(net.id, target_name, **target_kwargs)

        return net.id, caller_p.id, target_p.id

    async def get_network(self, network_id: str) -> Network:
        """Get a network by ID."""
        try:
            response = await self._http_client.get(f"/networks/{network_id}")
            response.raise_for_status()
            return Network(**self._norm_network(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Network '{network_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def delete_network(self, network_id: str) -> None:
        """Delete a network. Only the owner can delete."""
        try:
            response = await self._http_client.delete(f"/networks/{network_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Network '{network_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except httpx.RequestError as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def leave_network(self, network_id: str, participant_id: str) -> None:
        """Remove a participant from a network."""
        try:
            response = await self._http_client.delete(
                f"/networks/{network_id}/participants/{participant_id}"
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Participant '{participant_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except httpx.RequestError as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_network_context(
        self, network_id: str, limit: int = 50
    ) -> NetworkContext:
        """Read the shared context of a network (recent messages, ordered).

        Useful for late-joining participants or summarization.
        """
        try:
            response = await self._http_client.get(
                f"/networks/{network_id}/context", params={"limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            entries = [ContextEntry(**self._norm_context_entry(e)) for e in data.get("entries", [])]
            return NetworkContext(network_id=str(data.get("network_id", network_id)), entries=entries)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def send_to_mailbox(
        self,
        network_id: str,
        sender_participant_id: str,
        recipient_participant_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NetworkMessage:
        """Send a mailbox message (fully async — stored without push delivery).

        The recipient reads via ``get_inbox``. Use for fire-and-forget or when
        the recipient has no callback URL.
        """
        body: Dict[str, Any] = {
            "sender_participant_id": sender_participant_id,
            "recipient_participant_id": recipient_participant_id,
            "content": content,
        }
        if metadata:
            body["metadata"] = metadata
        try:
            response = await self._http_client.post(
                f"/networks/{network_id}/mailbox", json=body
            )
            response.raise_for_status()
            return NetworkMessage(**self._norm_net_msg(response.json()))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Mailbox send failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def get_inbox(
        self,
        network_id: str,
        participant_id: str,
        channel_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[NetworkMessage]:
        """Poll inbox for a participant. Returns unread messages only.

        Pair with ``acknowledge_messages`` to mark them as read.
        """
        params: Dict[str, Any] = {"limit": limit}
        if channel_type:
            params["channel_type"] = channel_type
        try:
            response = await self._http_client.get(
                f"/networks/{network_id}/inbox/{participant_id}", params=params
            )
            response.raise_for_status()
            return [NetworkMessage(**self._norm_net_msg(m)) for m in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def acknowledge_messages(
        self, network_id: str, message_ids: List[str]
    ) -> int:
        """Mark messages as read. Returns the number actually acknowledged."""
        try:
            response = await self._http_client.post(
                f"/networks/{network_id}/messages/ack",
                json={"message_ids": message_ids},
            )
            response.raise_for_status()
            return int(response.json().get("acknowledged", 0))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Ack failed: {e.response.text}") from e
        except httpx.RequestError as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── A2A agent import ─────────────────────────────────────────────

    async def preview_a2a_card(self, url: str) -> Dict[str, Any]:
        """Fetch an A2A Agent Card from a URL without importing it.

        Returns the card dict. Use this to inspect capabilities before
        calling ``import_a2a_agent``.
        """
        try:
            response = await self._http_client.get(
                "/a2a/agents/fetch-card", params={"url": url}
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                raise IntunoError(data.get("error", "Failed to fetch Agent Card"))
            return data.get("card", {})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"Failed to fetch card: {e.response.text}") from e
        except httpx.RequestError as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def import_a2a_agent(self, url: str) -> Agent:
        """Import an external A2A agent by URL.

        Fetches the Agent Card, registers the agent, and indexes it for
        semantic discovery. The returned ``Agent`` is fully discoverable
        via ``discover()`` and invocable via ``invoke()``.
        """
        try:
            response = await self._http_client.post(
                "/a2a/agents/import", json={"url": url}
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                raise IntunoError(data.get("error", "Import failed"))
            # Backend returns a subset of Agent fields; fetch full record for consistency.
            return await self.get_agent(data["agent_id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            raise IntunoError(f"A2A import failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    async def refresh_a2a_agent(self, agent_id: str) -> Agent:
        """Re-fetch an imported A2A agent's card and update its registry entry."""
        try:
            response = await self._http_client.post(
                f"/a2a/agents/{agent_id}/refresh"
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                raise IntunoError(data.get("error", "Refresh failed"))
            return await self.get_agent(data["agent_id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key.") from e
            if e.response.status_code == 404:
                raise IntunoError(f"Agent '{agent_id}' not found.") from e
            raise IntunoError(f"API request failed: {e.response.text}") from e
        except (httpx.RequestError, ValidationError) as e:
            raise IntunoError(f"An unexpected error occurred: {e}") from e

    # ── Normalizers ──────────────────────────────────────────────────

    @staticmethod
    def _norm_network(obj: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(obj)
        for k in ("id", "owner_id"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        for k in ("created_at", "updated_at"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        return out

    @staticmethod
    def _norm_participant(obj: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(obj)
        for k in ("id", "network_id", "agent_id"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        for k in ("created_at", "updated_at"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        return out

    @staticmethod
    def _norm_net_msg(obj: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(obj)
        for k in ("id", "network_id", "sender_participant_id", "recipient_participant_id", "in_reply_to_id"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        for k in ("created_at", "updated_at"):
            if k in out and out[k] is not None:
                out[k] = str(out[k])
        return out

    @staticmethod
    def _norm_context_entry(obj: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(obj)
        if "message_id" in out and out["message_id"] is not None:
            out["message_id"] = str(out["message_id"])
        if "timestamp" in out and out["timestamp"] is not None:
            out["timestamp"] = str(out["timestamp"])
        return out

    async def close(self):
        """Closes the underlying HTTP client."""
        await self._http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
