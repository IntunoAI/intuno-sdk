from typing import Any, Dict, List

import httpx
from pydantic import ValidationError

from src.intuno_sdk.constants import DEFAULT_BASE_URL
from src.intuno_sdk.exceptions import (
    APIKeyMissingError,
    AuthenticationError,
    InvocationError,
    IntunoError,
)
from src.intuno_sdk.models import Agent, InvokeResult


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
                "User-Agent": "Intuno-SDK/0.1.0",
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
    ) -> InvokeResult:
        """
        Invoke an agent's capability.

        Args:
            agent_id: The ID of the agent to invoke.
            capability_id: The ID of the capability to use.
            input_data: A dictionary containing the input for the capability.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        payload = {
            "agent_id": agent_id,
            "capability_id": capability_id,
            "input": input_data,
        }
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
                "User-Agent": "Intuno-SDK/0.1.0",
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
    ) -> InvokeResult:
        """
        Asynchronously invoke an agent's capability.

        Args:
            agent_id: The ID of the agent to invoke.
            capability_id: The ID of the capability to use.
            input_data: A dictionary containing the input for the capability.

        Returns:
            An InvokeResult object with the outcome of the call.
        """
        payload = {
            "agent_id": agent_id,
            "capability_id": capability_id,
            "input": input_data,
        }
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

    async def close(self):
        """Closes the underlying HTTP client."""
        await self._http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
