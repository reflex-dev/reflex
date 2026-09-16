# Generated from packages/reflex-sdk/src/reflex_sdk/_async/_client.py by scripts/unasync_reflex_sdk.py. Do not edit.
"""The synchronous Reflex Cloud client."""

from __future__ import annotations

import time
from types import TracebackType
from typing import Any, TypeVar, overload

import httpx

from reflex_sdk._base import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    UNSENT_REQUEST_ERRORS,
    BaseClient,
    decode_response,
    logger,
)
from reflex_sdk._errors import (
    APIConnectionError,
    APITimeoutError,
    status_error_from_response,
)
from reflex_sdk._sync.resources.auth import Auth

T = TypeVar("T")


class ReflexCloud(BaseClient):
    """Client for the Reflex Cloud API.

    Use it as a context manager, or call ``close()``, to release its connections.
    """

    # The identity of the access token, and the token management endpoints.
    auth: Auth

    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Create a client.

        Args:
            token: The access token. Defaults to the ``REFLEX_ACCESS_TOKEN`` environment
                variable, then to the token saved by ``reflex login``.
            base_url: The Reflex Cloud URL. Defaults to the ``REFLEX_CLOUD_BACKEND_URL``
                environment variable, then to ``https://build.reflex.dev``.
            timeout: The timeout of each request attempt, in seconds. Defaults to the
                timeout of ``http_client`` when one is passed, and to 60 seconds, 10 of
                them to connect, otherwise.
            max_retries: How many times a failed request is retried. Only requests that
                cannot be applied twice are retried: those the server never received or
                processed, and idempotent ``GET``, ``HEAD``, ``OPTIONS`` and ``PUT`` requests.
            http_client: An HTTP client to send requests with, e.g. to configure proxies.
                The caller keeps ownership of it: closing this client leaves it open.
        """
        super().__init__(
            token=token, base_url=base_url, timeout=timeout, max_retries=max_retries
        )
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=DEFAULT_TIMEOUT)
        self.auth = Auth(self)

    def __enter__(self) -> ReflexCloud:
        """Enter the client's context.

        Returns:
            The client.
        """
        return self

    def __exit__(
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
        self.close()

    def close(self) -> None:
        """Close the connections of the HTTP client, unless it was passed in."""
        if self._owns_http_client:
            self._http_client.close()

    @overload
    def _request(
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
    def _request(
        self,
        method: str,
        path: str,
        cast: None,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        authenticated: bool = True,
    ) -> None: ...

    def _request(
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
            params: The query parameters.
            json: The JSON body, if any.
            authenticated: Whether to send the access token.

        Returns:
            The decoded response body.

        Raises:
            APITimeoutError: If the last attempt timed out.
            APIConnectionError: If the last attempt could not reach the API.
            APIStatusError: If the API responded with an error status.
        """
        request = self._build_request(
            self._http_client,
            method,
            path,
            params=params,
            json=json,
            authenticated=authenticated,
        )
        attempt = 0
        while True:
            try:
                response = self._http_client.send(request)
            except httpx.TransportError as ex:
                delay = self._retry_delay(
                    request, attempt, sent=not isinstance(ex, UNSENT_REQUEST_ERRORS)
                )
                if delay is None:
                    if isinstance(ex, httpx.TimeoutException):
                        msg = f"{method} {request.url} timed out"
                        raise APITimeoutError(msg, request=request) from ex
                    msg = f"{method} {request.url} failed: {ex}"
                    raise APIConnectionError(msg, request=request) from ex
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
            time.sleep(delay)
