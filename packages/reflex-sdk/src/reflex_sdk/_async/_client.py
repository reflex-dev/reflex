"""The asynchronous Reflex Cloud client."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any, TypeVar, overload

from reflex_sdk._async.resources.apps import AsyncApps
from reflex_sdk._async.resources.auth import AsyncAuth
from reflex_sdk._async.resources.projects import AsyncProjects
from reflex_sdk._base import DEFAULT_MAX_RETRIES, BaseClient, decode_response, logger
from reflex_sdk._errors import (
    APIConnectionError,
    APITimeoutError,
    status_error_from_response,
)
from reflex_sdk.transports._base import AsyncTransport, TransportError
from reflex_sdk.transports._defaults import AsyncDefaultTransport

T = TypeVar("T")


class AsyncReflexCloud(BaseClient):
    """Client for the Reflex Cloud API.

    Use it as a context manager, or call ``aclose()``, to release its connections.
    """

    # Manage apps, their lifecycle, deployment history, logs and secrets.
    apps: AsyncApps
    # The identity of the access token, and the token management endpoints.
    auth: AsyncAuth
    # Manage projects and who has access to them.
    projects: AsyncProjects

    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: AsyncTransport | None = None,
    ) -> None:
        """Create a client.

        Args:
            token: The access token. Defaults to the ``REFLEX_ACCESS_TOKEN`` environment
                variable, then to the token saved by ``reflex login``.
            base_url: The Reflex Cloud URL. Defaults to the ``REFLEX_CLOUD_BACKEND_URL``
                environment variable, then to ``https://build.reflex.dev``.
            timeout: The timeout of each request attempt, in seconds. Defaults to the
                transport's timeout, 60 seconds (10 of them to connect) for the
                transports the SDK creates.
            max_retries: How many times a failed request is retried. Only requests that
                cannot be applied twice are retried: those the server never received or
                turned away with 408 or 429, and ``GET``, ``HEAD``, ``OPTIONS`` and ``PUT``
                requests that timed out, lost their connection, or got a 500, 502, 503
                or 504 response.
            transport: Sends the requests, e.g. a transport wrapping a preconfigured
                HTTP client. The caller keeps ownership of it: closing this client
                leaves it open. Defaults to a transport the client creates and closes.
        """
        super().__init__(
            token=token, base_url=base_url, timeout=timeout, max_retries=max_retries
        )
        self._owns_transport = transport is None
        self._transport = AsyncDefaultTransport() if transport is None else transport
        self.apps = AsyncApps(self)
        self.auth = AsyncAuth(self)
        self.projects = AsyncProjects(self)

    async def __aenter__(self) -> AsyncReflexCloud:
        """Enter the client's context.

        Returns:
            The client.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the client when leaving its context.

        Args:
            exc_type: The type of the exception raised in the context, if any.
            exc: The exception raised in the context, if any.
            traceback: The traceback of that exception, if any.
        """
        await self.aclose()

    async def aclose(self) -> None:
        """Close the transport, unless it was passed in."""
        if self._owns_transport:
            await self._transport.aclose()

    @overload
    async def _request(
        self,
        method: str,
        path: str,
        cast: type[T],
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        authenticated: bool = True,
    ) -> T: ...

    @overload
    async def _request(
        self,
        method: str,
        path: str,
        cast: None,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        authenticated: bool = True,
    ) -> None: ...

    async def _request(
        self,
        method: str,
        path: str,
        cast: Any,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        authenticated: bool = True,
    ) -> Any:
        """Send an API request, retrying transient failures that are safe to retry.

        Args:
            method: The HTTP method.
            path: The endpoint path relative to ``/api/v1/``, with path parameters
                already quoted.
            cast: The type to decode the JSON response into, or None to ignore it.
            params: The query parameters; None values are left out.
            json: The JSON body, if any.
            authenticated: Whether to send the access token.

        Returns:
            The decoded response body.

        Raises:
            APITimeoutError: If the last attempt timed out.
            APIConnectionError: If the last attempt failed without a response.
            APIStatusError: If the API responded with an error status.
        """
        request = self._build_request(
            method, path, params=params, json=json, authenticated=authenticated
        )
        attempt = 0
        while True:
            try:
                response = await self._transport.send(request)
            except TransportError as ex:
                delay = self._retry_delay(request, attempt, sent=ex.sent)
                if delay is None:
                    error_type = APITimeoutError if ex.timed_out else APIConnectionError
                    msg = f"{method} {request.url} failed: {ex}"
                    raise error_type(msg, request=request) from ex
            else:
                if response.is_success:
                    return decode_response(response, cast)
                delay = self._retry_delay(request, attempt, response)
                if delay is None:
                    raise status_error_from_response(response)
            attempt += 1
            logger.debug(
                "Retrying %s %s in %.2fs (retry %d of %d)",
                method,
                request.url,
                delay,
                attempt,
                self.max_retries,
            )
            await asyncio.sleep(delay)
