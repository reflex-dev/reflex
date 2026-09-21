"""Transports built on httpx."""

from __future__ import annotations

import httpx

from reflex_build_sdk.transports._base import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_TIMEOUT,
    Request,
    Response,
    TransportError,
)

# Raised before the request left the client, so the server never saw it.
_UNSENT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


def _default_timeout() -> httpx.Timeout:
    return httpx.Timeout(DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)


def _build_request(
    client: httpx.Client | httpx.AsyncClient, request: Request
) -> httpx.Request:
    return client.build_request(
        request.method,
        request.url,
        headers=request.headers,
        content=request.content,
        timeout=httpx.USE_CLIENT_DEFAULT
        if request.timeout is None
        else request.timeout,
    )


def _to_response(request: Request, response: httpx.Response) -> Response:
    return Response(
        request=request,
        status_code=response.status_code,
        reason_phrase=response.reason_phrase,
        headers={name.lower(): value for name, value in response.headers.items()},
        content=response.content,
    )


def _to_error(request: Request, error: httpx.TransportError) -> TransportError:
    return TransportError(
        str(error) or type(error).__name__,
        request=request,
        sent=not isinstance(error, _UNSENT_ERRORS),
        timed_out=isinstance(error, httpx.TimeoutException),
    )


class HttpxTransport:
    """Sends the synchronous client's requests with an ``httpx.Client``."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        """Create the transport.

        Args:
            client: The HTTP client to send requests with, e.g. to configure proxies.
                The caller keeps ownership of it: closing the transport leaves it open.
                Defaults to a client the transport creates and closes.
        """
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=_default_timeout())

    def send(self, request: Request) -> Response:
        """Send a request and read the whole response.

        Args:
            request: The request.

        Returns:
            The response, whatever its status code.

        Raises:
            TransportError: If the request failed without getting a response.
        """
        try:
            response = self._client.send(_build_request(self._client, request))
        except httpx.TransportError as ex:
            raise _to_error(request, ex) from ex
        return _to_response(request, response)

    def close(self) -> None:
        """Close the HTTP client, unless it was passed in."""
        if self._owns_client:
            self._client.close()


class AsyncHttpxTransport:
    """Sends the asynchronous client's requests with an ``httpx.AsyncClient``."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Create the transport.

        Args:
            client: The HTTP client to send requests with, e.g. to configure proxies.
                The caller keeps ownership of it: closing the transport leaves it open.
                Defaults to a client the transport creates and closes.
        """
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=_default_timeout())

    async def send(self, request: Request) -> Response:
        """Send a request and read the whole response.

        Args:
            request: The request.

        Returns:
            The response, whatever its status code.

        Raises:
            TransportError: If the request failed without getting a response.
        """
        try:
            response = await self._client.send(_build_request(self._client, request))
        except httpx.TransportError as ex:
            raise _to_error(request, ex) from ex
        return _to_response(request, response)

    async def aclose(self) -> None:
        """Close the HTTP client, unless it was passed in."""
        if self._owns_client:
            await self._client.aclose()
