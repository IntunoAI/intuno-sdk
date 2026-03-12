from typing import Any, Dict, List, Optional

import httpx
from pydantic import ValidationError

from src.intuno_sdk.constants import DEFAULT_BASE_URL
from src.intuno_sdk.exceptions import (
    APIKeyMissingError,
    AuthenticationError,
    InvocationError,
    IntunoError,
)
from src.intuno_sdk.models import Agent, InvokeResult, TaskResult


class IntunoClient:
    """
    The main synchronous client for interacting with the Intuno Agent Network.
    """

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL):
        if not api_key:
            raise APIKeyMissingError()

        self.api_key = api_key
        self.base_url = base_url
        self._http_client = httpx.Client(
            base_url=self.base_url,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "Intuno-SDK/0.2.0",
            },
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
        capability_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
    ) -> InvokeResult:
        """
        Invoke an agent's capability.

        Args:
            agent_id: The ID of the agent to invoke.
            capability_id: The ID of the capability to use.
            input_data: A dictionary containing the input for the capability.
            conversation_id: Optional conversation ID to attach this invocation to.
            message_id: Optional message ID within the conversation.
            external_user_id: Optional end-user ID for multi-user apps.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "capability_id": capability_id,
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
    """

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL):
        if not api_key:
            raise APIKeyMissingError()

        self.api_key = api_key
        self.base_url = base_url
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "Intuno-SDK/0.2.0",
            },
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
        capability_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
    ) -> InvokeResult:
        """
        Asynchronously invoke an agent's capability.

        Args:
            agent_id: The ID of the agent to invoke.
            capability_id: The ID of the capability to use.
            input_data: A dictionary containing the input for the capability.
            conversation_id: Optional conversation ID to attach this invocation to.
            message_id: Optional message ID within the conversation.
            external_user_id: Optional end-user ID for multi-user apps.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "capability_id": capability_id,
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

    async def close(self):
        """Closes the underlying HTTP client."""
        await self._http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
