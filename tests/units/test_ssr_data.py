"""Unit tests for the /_ssr_data endpoint handler."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.responses import Response

import reflex as rx
from reflex.app import App, ssr_data
from reflex.state import State, all_base_state_classes


@pytest.fixture(autouse=True, scope="module")
def _clean_state_subclasses():
    """Snapshot and restore State subclass registrations after all tests.

    Tests in this module define rx.State subclasses inside test functions,
    which permanently registers them in the global class hierarchy.  Without
    cleanup, these leak into later test modules (e.g. test_state.py) and
    cause failures.
    """
    orig_subclasses = State.class_subclasses.copy()
    orig_all = all_base_state_classes.copy()
    orig_dirty = State._potentially_dirty_states.copy()
    orig_always_dirty = State._always_dirty_substates.copy()
    orig_var_deps = State._var_dependencies.copy()

    yield

    State.class_subclasses = orig_subclasses
    State._potentially_dirty_states = orig_dirty
    State._always_dirty_substates = orig_always_dirty
    State._var_dependencies = orig_var_deps
    all_base_state_classes.clear()
    all_base_state_classes.update(orig_all)
    State.get_class_substate.cache_clear()


def _make_request(path: str = "/", headers: dict | None = None) -> Mock:
    """Create a mock Starlette Request with the given path and headers.

    Args:
        path: The URL path to include in the request body.
        headers: Optional headers dict to include in the request body.

    Returns:
        A mock Request object.
    """
    body = {"path": path, "headers": headers or {}}
    request = Mock()
    request.json = AsyncMock(return_value=body)
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


def _parse_response(response: Response) -> dict[str, Any]:
    """Parse a Starlette Response body as JSON.

    Args:
        response: The response to parse.

    Returns:
        Parsed JSON as a dict.
    """
    assert isinstance(response.body, bytes)
    return json.loads(response.body)


@pytest.mark.asyncio
async def test_ssr_data_no_state():
    """When the app has no state, the endpoint returns null state."""
    app = App(enable_state=False)
    app.add_page(lambda: rx.text("hello"), route="/")
    handler = ssr_data(app)

    response = await handler(_make_request("/"))

    assert response.status_code == 200
    data = _parse_response(response)
    assert data["state"] is None


@pytest.mark.asyncio
async def test_ssr_data_basic_state():
    """The endpoint returns serialized state for a basic stateful app."""

    class BasicState(rx.State):
        title: str = "default"

    app = App()
    app._state = BasicState
    app.add_page(lambda: rx.text(BasicState.title), route="/")

    handler = ssr_data(app)
    response = await handler(_make_request("/"))

    assert response.status_code == 200
    data = _parse_response(response)
    assert data["state"] is not None

    # The root State should be present.
    root_name = rx.State.get_full_name()
    assert root_name in data["state"]

    # The user's substate should also be present with the default value.
    substate_name = BasicState.get_full_name()
    assert substate_name in data["state"]
    assert data["state"][substate_name]["title_rx_state_"] == "default"


@pytest.mark.asyncio
async def test_ssr_data_dynamic_route_params():
    """Route params are extracted from the URL path and set on the state."""

    class PostState(rx.State):
        pass

    app = App()
    app._state = PostState
    app.add_page(lambda: rx.text("post"), route="/blog/[slug]")

    handler = ssr_data(app)
    response = await handler(_make_request("/blog/hello-world"))

    assert response.status_code == 200
    data = _parse_response(response)
    root_name = rx.State.get_full_name()
    router = data["state"][root_name]["router_rx_state_"]
    assert router["page"]["params"] == {"slug": "hello-world"}
    assert router["page"]["raw_path"] == "/blog/hello-world"


@pytest.mark.asyncio
async def test_ssr_data_on_load_runs():
    """The on_load handler runs and mutates state before serialization."""

    class LoadState(rx.State):
        title: str = ""

        @rx.event
        def on_load_post(self):
            self.title = "loaded"

    app = App()
    app._state = LoadState
    app.add_page(
        lambda: rx.text(LoadState.title),
        route="/page",
        on_load=LoadState.on_load_post,
    )

    handler = ssr_data(app)
    response = await handler(_make_request("/page"))

    assert response.status_code == 200
    data = _parse_response(response)
    substate_name = LoadState.get_full_name()
    assert data["state"][substate_name]["title_rx_state_"] == "loaded"


@pytest.mark.asyncio
async def test_ssr_data_async_on_load():
    """An async on_load handler is properly awaited."""

    class AsyncLoadState(rx.State):
        message: str = ""

        @rx.event
        async def load_data(self):
            self.message = "async-loaded"

    app = App()
    app._state = AsyncLoadState
    app.add_page(
        lambda: rx.text(AsyncLoadState.message),
        route="/async",
        on_load=AsyncLoadState.load_data,
    )

    handler = ssr_data(app)
    response = await handler(_make_request("/async"))

    assert response.status_code == 200
    data = _parse_response(response)
    substate_name = AsyncLoadState.get_full_name()
    assert data["state"][substate_name]["message_rx_state_"] == "async-loaded"


@pytest.mark.asyncio
async def test_ssr_data_on_load_error_graceful():
    """If on_load raises, the endpoint returns state with defaults (no crash)."""

    class ErrorState(rx.State):
        value: str = "untouched"

        @rx.event
        def bad_handler(self):
            msg = "boom"
            raise RuntimeError(msg)

    app = App()
    app._state = ErrorState
    app.add_page(
        lambda: rx.text(ErrorState.value),
        route="/error",
        on_load=ErrorState.bad_handler,
    )

    handler = ssr_data(app)
    response = await handler(_make_request("/error"))

    assert response.status_code == 200
    data = _parse_response(response)
    substate_name = ErrorState.get_full_name()
    # State should still be returned with original defaults.
    assert data["state"][substate_name]["value_rx_state_"] == "untouched"


@pytest.mark.asyncio
async def test_ssr_data_headers_forwarded():
    """Request headers are set on the state's router headers."""

    class HeaderState(rx.State):
        pass

    app = App()
    app._state = HeaderState
    app.add_page(lambda: rx.text("h"), route="/")

    handler = ssr_data(app)
    response = await handler(
        _make_request(
            "/", headers={"user-agent": "Googlebot", "origin": "https://example.com"}
        )
    )

    assert response.status_code == 200
    data = _parse_response(response)
    root_name = rx.State.get_full_name()
    router = data["state"][root_name]["router_rx_state_"]
    assert router["headers"]["user_agent"] == "Googlebot"


@pytest.mark.asyncio
async def test_ssr_data_unknown_route():
    """An unknown path resolves to the 404 route."""

    class NotFoundState(rx.State):
        pass

    app = App()
    app._state = NotFoundState
    app.add_page(lambda: rx.text("home"), route="/")

    handler = ssr_data(app)
    response = await handler(_make_request("/this/does/not/exist"))

    assert response.status_code == 200
    data = _parse_response(response)
    # Should still return valid state (the 404 handler path).
    assert data["state"] is not None


@pytest.mark.asyncio
async def test_ssr_data_cache_control_header():
    """The response includes Cache-Control: no-cache."""

    class CacheState(rx.State):
        pass

    app = App()
    app._state = CacheState
    app.add_page(lambda: rx.text("c"), route="/")

    handler = ssr_data(app)
    response = await handler(_make_request("/"))

    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_ssr_data_client_ip():
    """The client IP from the request is set in the state."""

    class IpState(rx.State):
        pass

    app = App()
    app._state = IpState
    app.add_page(lambda: rx.text("ip"), route="/")

    handler = ssr_data(app)
    request = _make_request("/")
    request.client.host = "10.0.0.42"
    response = await handler(request)

    assert response.status_code == 200
    data = _parse_response(response)
    root_name = rx.State.get_full_name()
    router = data["state"][root_name]["router_rx_state_"]
    assert router["session"]["client_ip"] == "10.0.0.42"
