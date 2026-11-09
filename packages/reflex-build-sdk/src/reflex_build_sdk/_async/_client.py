"""The asynchronous Reflex Build client."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from types import TracebackType
from typing import Any, TypeVar, overload

from reflex_build_sdk._async.resources.apps import AsyncApps
from reflex_build_sdk._async.resources.auth import AsyncAuth
from reflex_build_sdk._async.resources.deployments import AsyncDeployments
from reflex_build_sdk._async.resources.projects import AsyncProjects
from reflex_build_sdk._async.resources.providers import AsyncProviders
from reflex_build_sdk._async.resources.security_reviews import AsyncSecurityReviews
from reflex_build_sdk._async.resources.usage import AsyncUsage
from reflex_build_sdk._base import (
    DEFAULT_MAX_RETRIES,
    BaseClient,
    connection_error,
    decode_response,
    logger,
)
from reflex_build_sdk._errors import status_error_from_response
from reflex_build_sdk.transports._base import AsyncTransport, TransportError
from reflex_build_sdk.transports._defaults import async_default_transport

T = TypeVar("T")


class AsyncReflexBuild(BaseClient):
    """Client for the Reflex Build API.

    Use it as a context manager, or call ``aclose()``, to release its connections.
    """

    # Manage apps, their lifecycle, deployment history, logs and secrets.
    apps: AsyncApps
    # The identity of the access token, and the token management endpoints.
    auth: AsyncAuth
    # Deploy apps and follow their deployments.
    deployments: AsyncDeployments
    # Manage projects and who has access to them.
    projects: AsyncProjects
    # Read the cloud providers an organization deploys apps to.
    providers: AsyncProviders
    # Review an app's source code for security and logic issues.
    security_reviews: AsyncSecurityReviews
    # Read an organization's use of its plan allowance.
    usage: AsyncUsage

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
                variable.
            base_url: The Reflex Build URL. Defaults to the ``REFLEX_BUILD_BACKEND_URL``
                environment variable, then to ``REFLEX_CLOUD_BACKEND_URL``, which
                ``reflex-hosting-cli`` reads, then to ``https://build.reflex.dev``.
            timeout: The timeout of each network operation (connecting, or any single
                read or write), in seconds. Defaults to the transport's timeouts: 10
                seconds to connect and 60 for a read or write for the transports the
                SDK creates.
            max_retries: How many times a failed request is retried. Only requests that
                cannot be applied twice are retried: those the server never received or
                turned away with 408 or 429, and requests that are harmless to repeat
                (``GET``, ``HEAD``, ``OPTIONS`` and ``PUT`` requests, and calls such as
                ``apps.environments.update`` that settle on the same result) that
                timed out, lost their connection, or got a 500, 502, 503 or 504
                response.
            transport: Sends the requests, e.g. a transport wrapping a preconfigured
                HTTP client. The caller keeps ownership of it: closing this client
                leaves it open. Defaults to a transport the client creates and closes.
        """
        super().__init__(
            token=token, base_url=base_url, timeout=timeout, max_retries=max_retries
        )
        self._owns_transport = transport is None
        self._transport = async_default_transport() if transport is None else transport
        self.apps = AsyncApps(self)
        self.auth = AsyncAuth(self)
        self.deployments = AsyncDeployments(self)
        self.projects = AsyncProjects(self)
        self.providers = AsyncProviders(self)
        self.security_reviews = AsyncSecurityReviews(self)
        self.usage = AsyncUsage(self)

    async def __aenter__(self) -> AsyncReflexBuild:
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
        form: Mapping[str, str] | None = None,
        authenticated: bool = True,
        idempotent: bool | None = None,
        extra_headers: Mapping[str, str] | None = None,
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
        form: Mapping[str, str] | None = None,
        authenticated: bool = True,
        idempotent: bool | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None: ...

    async def _request(
        self,
        method: str,
        path: str,
        cast: Any,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        form: Mapping[str, str] | None = None,
        authenticated: bool = True,
        idempotent: bool | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Send an API request, retrying transient failures that are safe to retry.

        Args:
            method: The HTTP method.
            path: The endpoint path relative to ``/api/v1/``, with path parameters
                already quoted.
            cast: The type to decode the JSON response into, None to ignore it, or
                ``Response`` for the response itself.
            params: The query parameters; None values are left out.
            json: The JSON body, if any.
            form: A form-encoded body, sent instead of ``json``.
            authenticated: Whether to send the access token.
            idempotent: Whether repeating the request is harmless, which decides
                whether it is retried after it may have reached the server. Defaults
                to whether the method is idempotent.
            extra_headers: Headers to send beside the ones every request carries.

        Returns:
            The decoded response body.

        Raises:
            APITimeoutError: If the last attempt timed out.
            APIConnectionError: If the last attempt failed without a response.
            APIStatusError: If the API responded with an error status.
        """
        request = self._build_request(
            method,
            path,
            params=params,
            json=json,
            form=form,
            authenticated=authenticated,
            extra_headers=extra_headers,
        )
        attempt = 0
        while True:
            try:
                response = await self._transport.send(request)
            except TransportError as ex:
                delay = self._retry_delay(
                    request, attempt, sent=ex.sent, idempotent=idempotent
                )
                if delay is None:
                    raise connection_error(ex) from ex
            else:
                if response.is_success:
                    return decode_response(response, cast)
                delay = self._retry_delay(
                    request, attempt, response, idempotent=idempotent
                )
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
