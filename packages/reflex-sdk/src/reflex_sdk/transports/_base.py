"""The interface between the Reflex Cloud clients and an HTTP library."""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

# The timeouts of each network operation when neither the client nor the
# transport's own HTTP client sets them: 10 seconds to connect, and 60 seconds for
# any single read or write. They bound a stalled connection, not a whole request,
# so a large upload on a slow but working link is not cut off.
DEFAULT_TIMEOUT = 60.0
DEFAULT_CONNECT_TIMEOUT = 10.0


@dataclass(frozen=True, slots=True, kw_only=True)
class Request:
    """An HTTP request for a transport to send."""

    method: str
    # The absolute URL, with the path and query already encoded.
    url: str
    headers: Mapping[str, str]
    # The body, either whole or as chunks: an ``Iterable`` for synchronous
    # transports, an ``AsyncIterable`` for asynchronous ones. A streamed body is
    # sent with the ``Content-Length`` header the caller sets, and can only be
    # sent once.
    content: bytes | Iterable[bytes] | AsyncIterable[bytes] | None = None
    # The timeout of each network operation in seconds, or None for the
    # transport's defaults.
    timeout: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Response:
    """An HTTP response received by a transport."""

    request: Request
    status_code: int
    reason_phrase: str
    # Header names are lowercase.
    headers: Mapping[str, str]
    content: bytes

    @property
    def is_success(self) -> bool:
        """Whether the status code is 2xx.

        Returns:
            True for a successful response.
        """
        return 200 <= self.status_code < 300

    @property
    def text(self) -> str:
        """The body decoded as UTF-8.

        Returns:
            The body text, with undecodable bytes replaced.
        """
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Parse the body as JSON.

        Returns:
            The parsed body.
        """
        return json.loads(self.content)


class TransportError(Exception):
    """A request failed without getting a response."""

    request: Request
    # Whether the request may have reached the server. A request that never did
    # can be retried whatever its method.
    sent: bool
    timed_out: bool

    def __init__(
        self, message: str, *, request: Request, sent: bool, timed_out: bool = False
    ) -> None:
        """Initialize the error.

        Args:
            message: What went wrong.
            request: The request that failed.
            sent: Whether the request may have reached the server.
            timed_out: Whether the request failed by timing out.
        """
        super().__init__(message)
        self.request = request
        self.sent = sent
        self.timed_out = timed_out


class Transport(Protocol):
    """Sends requests for the synchronous client."""

    def send(self, request: Request) -> Response:
        """Send a request and read the whole response.

        Args:
            request: The request.

        Returns:
            The response, whatever its status code.

        Raises:
            TransportError: If the request failed without getting a response.
        """
        ...

    def close(self) -> None:
        """Release the connections the transport holds."""
        ...


class AsyncTransport(Protocol):
    """Sends requests for the asynchronous client."""

    async def send(self, request: Request) -> Response:
        """Send a request and read the whole response.

        Args:
            request: The request.

        Returns:
            The response, whatever its status code.

        Raises:
            TransportError: If the request failed without getting a response.
        """
        ...

    async def aclose(self) -> None:
        """Release the connections the transport holds."""
        ...
