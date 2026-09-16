"""Fixtures for the reflex-sdk tests."""

from __future__ import annotations

import json as json_module
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import reflex_sdk._base
import reflex_sdk._credentials
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

Handler = Callable[[Request], Response]


def reply(
    status_code: int,
    *,
    json: Any = None,
    text: str = "",
    headers: dict[str, str] | None = None,
    reason_phrase: str = "",
) -> Handler:
    """Build a handler answering every request with the same response.

    Args:
        status_code: The status code.
        json: A JSON body.
        text: A text body, used when ``json`` is None.
        headers: The response headers, with lowercase names.
        reason_phrase: The reason phrase.

    Returns:
        The handler.
    """
    content = (json_module.dumps(json) if json is not None else text).encode()

    def handle(request: Request) -> Response:
        return Response(
            request=request,
            status_code=status_code,
            reason_phrase=reason_phrase,
            headers=headers or {},
            content=content,
        )

    return handle


class MockAPI:
    """Serves canned responses to the SDK, failing on routes the real API does not have."""

    def __init__(self) -> None:
        """Start with no handlers and no recorded requests."""
        self.handlers: dict[tuple[str, str], list[Handler]] = {}
        self.requests: list[Request] = []
        self.closed = False

    def add(self, method: str, path: str, *handlers: Handler) -> None:
        """Queue handlers for a route; the last one keeps answering once the others are used.

        Args:
            method: The HTTP method.
            path: The encoded request path, including ``/api/v1``.
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
        path = urlsplit(request.url).path
        assert any(
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
        """Answer a request from the mock API.

        Args:
            request: The request.

        Returns:
            The response.
        """
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
        """Answer a request from the mock API.

        Args:
            request: The request.

        Returns:
            The response.
        """
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
    for name in ("REFLEX_ACCESS_TOKEN", "REFLEX_CLOUD_BACKEND_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        reflex_sdk._credentials,
        "credentials_path",
        lambda: tmp_path / "hosting_v1.json",
    )
    # Retries back off without waiting.
    monkeypatch.setattr(reflex_sdk._base, "_INITIAL_RETRY_DELAY", 0.0)
