"""Fixtures for the reflex-sdk tests."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import reflex_sdk._base
import reflex_sdk._credentials

OPENAPI_SNAPSHOT = Path(__file__).parents[3] / "packages/reflex-sdk/openapi.json"


def _load_routes() -> list[tuple[str, re.Pattern[str]]]:
    spec = json.loads(OPENAPI_SNAPSHOT.read_text())
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

Handler = httpx.Response | Callable[[httpx.Request], httpx.Response]


class MockAPI:
    """Serves canned responses to the SDK, failing on routes the real API does not have."""

    def __init__(self) -> None:
        """Start with no handlers and no recorded requests."""
        self.handlers: dict[tuple[str, str], list[Handler]] = {}
        self.requests: list[httpx.Request] = []

    def add(self, method: str, path: str, *handlers: Handler) -> None:
        """Queue responses for a route; the last one keeps answering once the others are used.

        Args:
            method: The HTTP method.
            path: The raw request path, including ``/api/v1``.
            handlers: Responses, or functions building one from the request.
        """
        self.handlers[method, path] = list(handlers)

    def transport(self) -> httpx.MockTransport:
        """Build a transport that routes requests to this mock.

        Returns:
            The transport, usable by sync and async HTTP clients.
        """
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.raw_path.decode().partition("?")[0]
        assert any(
            method == request.method and pattern.match(path)
            for method, pattern in ROUTES
        ), f"{request.method} {path} is not a route in openapi.json"
        handlers = self.handlers[request.method, path]
        handler = handlers.pop(0) if len(handlers) > 1 else handlers[0]
        return handler(request) if callable(handler) else handler


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
    for name in ("REFLEX_ACCESS_TOKEN", "REFLEX_CLOUD_BACKEND_URL", "CP_BACKEND_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        reflex_sdk._credentials,
        "credentials_path",
        lambda: tmp_path / "hosting_v1.json",
    )
    # Retries back off without waiting.
    monkeypatch.setattr(reflex_sdk._base, "_INITIAL_RETRY_DELAY", 0.0)
