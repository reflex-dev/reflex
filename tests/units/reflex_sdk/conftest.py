"""Fixtures for the reflex-sdk tests."""

from __future__ import annotations

import json as json_module
import re
from collections.abc import AsyncIterable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import reflex_sdk._base
import reflex_sdk.credentials
from reflex_sdk.transports import Request, Response

OPENAPI_SNAPSHOT = Path(__file__).parents[3] / "packages/reflex-sdk/openapi.json"


def _load_routes() -> list[tuple[str, re.Pattern[str]]]:
    spec = json_module.loads(OPENAPI_SNAPSHOT.read_text())
    return [
        (
            method.upper(),
            re.compile(
                "^/api" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(path)) + "$"
            ),
        )
        for path, operations in spec["paths"].items()
        for method in operations
    ]


ROUTES = _load_routes()
API_HOST = "build.reflex.dev"

Handler = Callable[[Request], Response]

# Tells an omitted JSON body apart from a JSON null body.
_NO_JSON: Any = object()


def reply(
    status_code: int,
    *,
    json: Any = _NO_JSON,
    text: str = "",
    headers: dict[str, str] | None = None,
    reason_phrase: str = "",
) -> Handler:
    """Build a handler answering every request with the same response.

    Args:
        status_code: The status code.
        json: A JSON body, which may be None to send ``null``.
        text: A text body, used when ``json`` is not given.
        headers: The response headers, with lowercase names.
        reason_phrase: The reason phrase.

    Returns:
        The handler.
    """
    content = (json_module.dumps(json) if json is not _NO_JSON else text).encode()

    def handle(request: Request) -> Response:
        return Response(
            request=request,
            status_code=status_code,
            reason_phrase=reason_phrase,
            headers=headers or {},
            content=content,
        )

    return handle


def json_body(request: Request) -> Any:
    """Parse the JSON body of a request the SDK built.

    Args:
        request: The request.

    Returns:
        The parsed body.
    """
    assert isinstance(request.content, bytes)
    return json_module.loads(request.content)


class MockAPI:
    """Serves canned responses to the SDK, failing on routes the real API does not have."""

    def __init__(self) -> None:
        """Start with no handlers and no recorded requests."""
        self.handlers: dict[tuple[str, str], list[Handler]] = {}
        self.requests: list[Request] = []
        # The streamed bodies the transports read, by request URL.
        self.uploads: dict[str, bytes] = {}
        self.closed = False

    def add(self, method: str, path: str, *handlers: Handler) -> None:
        """Queue handlers for a route; the last one keeps answering once the others are used.

        Args:
            method: The HTTP method.
            path: The encoded request path, including ``/api/v1`` for API routes.
            handlers: Functions building a response from the request, or raising
                ``TransportError``.
        """
        self.handlers[method, path] = list(handlers)

    def handle(self, request: Request) -> Response:
        """Answer a request with the next handler queued for its route.

        Args:
            request: The request.

        Returns:
            The response.
        """
        self.requests.append(request)
        url = urlsplit(request.url)
        path = url.path
        # Requests to other hosts, such as signed storage uploads, are not API routes.
        assert url.netloc != API_HOST or any(
            method == request.method and pattern.match(path)
            for method, pattern in ROUTES
        ), f"{request.method} {path} is not a route in openapi.json"
        handlers = self.handlers[request.method, path]
        handler = handlers.pop(0) if len(handlers) > 1 else handlers[0]
        return handler(request)


class MockTransport:
    """A synchronous transport answering from a mock API."""

    def __init__(self, api: MockAPI) -> None:
        """Bind the transport to a mock API.

        Args:
            api: The mock API.
        """
        self.api = api

    def send(self, request: Request) -> Response:
        """Read a streamed body, then answer the request from the mock API.

        Args:
            request: The request.

        Returns:
            The response.
        """
        if request.content is not None and not isinstance(request.content, bytes):
            assert not isinstance(request.content, AsyncIterable)
            self.api.uploads[request.url] = b"".join(request.content)
        return self.api.handle(request)

    def close(self) -> None:
        """Record that the transport was closed."""
        self.api.closed = True


class AsyncMockTransport:
    """An asynchronous transport answering from a mock API."""

    def __init__(self, api: MockAPI) -> None:
        """Bind the transport to a mock API.

        Args:
            api: The mock API.
        """
        self.api = api

    async def send(self, request: Request) -> Response:
        """Read a streamed body, then answer the request from the mock API.

        Args:
            request: The request.

        Returns:
            The response.
        """
        if request.content is not None and not isinstance(request.content, bytes):
            assert isinstance(request.content, AsyncIterable)
            self.api.uploads[request.url] = b"".join([
                chunk async for chunk in request.content
            ])
        return self.api.handle(request)

    async def aclose(self) -> None:
        """Record that the transport was closed."""
        self.api.closed = True


@pytest.fixture
def mock_api() -> MockAPI:
    """A mock of the Reflex Cloud API.

    Returns:
        The mock.
    """
    return MockAPI()


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the developer's environment and saved login out of the tests.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: A temporary directory standing in for the Reflex data directory.
    """
    for name in ("REFLEX_ACCESS_TOKEN", "REFLEX_CLOUD_BACKEND_URL", "REFLEX_CLOUD_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        reflex_sdk.credentials,
        "credentials_path",
        lambda: tmp_path / "hosting_v1.json",
    )
    # Retries back off without waiting.
    monkeypatch.setattr(reflex_sdk._base, "_INITIAL_RETRY_DELAY", 0.0)
