"""Test case for displaying the connection banner when the websocket drops."""

import contextlib
import json
import re
import time
from collections.abc import Callable, Generator, Iterator

import pytest
from playwright.sync_api import Page, WebSocketRoute, expect
from redis import Redis
from reflex_base import constants

from reflex.environment import environment
from reflex.istate.manager.redis import StateManagerRedis
from reflex.testing import AppHarness
from reflex.utils.token_manager import RedisTokenManager, TokenManager


def ConnectionBanner():
    """App with a connection banner."""
    import asyncio

    import reflex as rx

    class State(rx.State):
        foo: int = 0

        @rx.event
        def set_foo(self, foo: int):
            self.foo = foo

        @rx.event
        async def delay(self):
            await asyncio.sleep(5)

    def index():
        return rx.vstack(
            rx.text("Hello World"),
            rx.input(value=State.foo, read_only=True, id="counter"),
            rx.button(
                "Increment",
                id="increment",
                on_click=State.set_foo(State.foo + 1),
            ),
            rx.button("Delay", id="delay", on_click=State.delay),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(
    params=[constants.CompileContext.RUN, constants.CompileContext.DEPLOY],
    ids=["compile_context_run", "compile_context_deploy"],
)
def simulate_compile_context(request) -> constants.CompileContext:
    """Fixture to simulate reflex cloud deployment.

    Args:
        request: pytest request fixture.

    Returns:
        The context to run the app with.
    """
    return request.param


@pytest.fixture
def connection_banner(
    tmp_path,
    simulate_compile_context: constants.CompileContext,
) -> Generator[AppHarness, None, None]:
    """Start ConnectionBanner app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture
        simulate_compile_context: Which context to run the app with.

    Yields:
        running AppHarness instance
    """
    environment.REFLEX_COMPILE_CONTEXT.set(simulate_compile_context)

    with AppHarness.create(
        root=tmp_path,
        app_source=ConnectionBanner,
        app_name=(
            "connection_banner_reflex_cloud"
            if simulate_compile_context == constants.CompileContext.DEPLOY
            else "connection_banner"
        ),
    ) as harness:
        yield harness


@contextlib.contextmanager
def browser_offline(page: Page) -> Iterator[None]:
    """Temporarily take the browser context offline.

    Args:
        page: Playwright page.

    Yields:
        None
    """
    page.context.set_offline(True)
    try:
        yield
    finally:
        page.context.set_offline(False)


def _assert_token(connection_banner: AppHarness, page: Page) -> str:
    """Poll for backend to be up.

    Args:
        connection_banner: AppHarness instance.
        page: Playwright page.

    Returns:
        The token if found, raises an assertion error otherwise.
    """
    page.wait_for_function("() => sessionStorage.getItem('token') !== null")
    token = page.evaluate("() => sessionStorage.getItem('token')")
    assert token is not None, "token not found"
    return token


@pytest.fixture
def redis(
    connection_banner: AppHarness,
) -> Generator[Redis | None, None, None]:
    """Get the Redis instance from the StateManagerRedis used in the connection_banner test.

    Args:
        connection_banner: AppHarness instance.

    Yields:
        A Redis instance or None if the StateManager is not Redis.
    """
    from reflex.utils.prerequisites import get_redis_sync

    redis = None
    if (app := connection_banner.app_instance) is not None and isinstance(
        app.state_manager, StateManagerRedis
    ):
        redis = get_redis_sync()
    yield redis
    if redis is not None:
        with contextlib.suppress(Exception):
            redis.close()


def _assert_sockets(
    token_manager: TokenManager, redis: Redis | None, token: str, *sids: str
):
    """Assert which sockets the backend holds for a client token.

    Args:
        token_manager: The token manager of the app.
        redis: Redis instance used by the app, or None if not using Redis.
        token: The client token.
        sids: The Socket.IO session IDs expected to be linked, oldest first.
    """
    assert token_manager.token_to_sids.get(token, ()) == sids
    if redis is not None:
        assert isinstance(token_manager, RedisTokenManager)
        assert redis.smembers(token_manager._get_redis_key(token)) == {
            f"{token_manager.instance_id}:{sid}".encode() for sid in sids
        }


def test_connection_banner(
    connection_banner: AppHarness, redis: Redis | None, page: Page
):
    """Test that the connection banner is displayed when the websocket drops.

    Args:
        connection_banner: AppHarness instance.
        redis: Redis instance used by the app, or None if not using Redis.
        page: Playwright page.
    """
    assert connection_banner.app_instance is not None
    assert connection_banner.backend is not None
    assert connection_banner.frontend_url is not None
    page.goto(connection_banner.frontend_url)
    token = _assert_token(connection_banner, page)
    expect(page.get_by_text("Cannot connect to server")).to_have_count(0)

    # Check that the token association was established.
    app_token_manager = connection_banner.token_manager()
    (sid_before,) = app_token_manager.token_to_sids[token]
    _assert_sockets(app_token_manager, redis, token, sid_before)

    delay_button = page.locator("#delay")
    increment_button = page.locator("#increment")
    counter_element = page.locator("#counter")

    # Increment the counter
    increment_button.click()
    expect(counter_element).to_have_value("1")

    # Start a long event before blocking the network, to mark event_processing=true
    delay_button.click()

    with browser_offline(page):
        # Error modal should now be displayed
        expect(page.get_by_text("Cannot connect to server")).to_be_visible()

        # The token association should be removed once the websocket closes on the server.
        assert connection_banner._poll_for(
            lambda: token not in app_token_manager.token_to_sids
        )
        _assert_sockets(app_token_manager, redis, token)

        # Increment the counter while disconnected
        increment_button.click()
        expect(counter_element).to_have_value("1")

    # Banner should be gone now (network restored on context manager exit)
    expect(page.get_by_text("Cannot connect to server")).to_have_count(0)

    # After reconnecting, the token association should be re-established.
    app_token_manager = connection_banner.token_manager()
    # Make sure the new connection has a different websocket sid.
    (sid_after,) = app_token_manager.token_to_sids[token]
    assert sid_before != sid_after
    _assert_sockets(app_token_manager, redis, token, sid_after)

    # Count should have incremented after coming back up
    expect(counter_element).to_have_value("2")


def _poll_with_page(
    page: Page, target: Callable[[], bool], timeout: float = 10
) -> bool:
    """Poll a condition while Playwright keeps serving the page's routes.

    A route handler runs in this thread, so a plain sleep would stall the
    websockets the test relays.

    Args:
        page: Playwright page.
        target: The condition to wait for.
        timeout: The maximum time to wait in seconds.

    Returns:
        Whether the condition was met in time.
    """
    deadline = time.monotonic() + timeout
    while not (met := target()) and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    return met


def test_reconnect_before_old_socket_closes_keeps_session(
    connection_banner: AppHarness, redis: Redis | None, page: Page
):
    """State survives a reconnect that the backend sees before the old socket closes.

    Behind a reverse proxy the new websocket of a reconnect is regularly
    connected before the backend learns that the old one is gone. The client
    token then has two sockets for a while, which must keep the session: the
    client is not handed another token, and with it an empty state. A second
    tab holding the same token joins the session as well.

    Args:
        connection_banner: AppHarness instance.
        redis: Redis instance used by the app, or None if not using Redis.
        page: Playwright page.
    """
    assert connection_banner.frontend_url is not None
    # Both ends of every websocket of the page, so that one can be closed
    # while the other stays open.
    websockets: list[tuple[WebSocketRoute, WebSocketRoute]] = []
    # Websockets whose backend end stays open when their page end closes.
    held_open: list[WebSocketRoute] = []

    def proxy_websocket(page_side: WebSocketRoute):
        """Relay a websocket of the page to the backend.

        Args:
            page_side: The websocket as the page sees it.
        """
        backend_side = page_side.connect_to_server()

        def close_backend_side(code: int | None, reason: str | None):
            if page_side not in held_open:
                backend_side.close()

        page_side.on_close(close_backend_side)
        backend_side.on_close(lambda code, reason: page_side.close())
        websockets.append((page_side, backend_side))

    page.route_web_socket(re.compile(r"/_event"), proxy_websocket)
    page.goto(connection_banner.frontend_url)
    token = _assert_token(connection_banner, page)
    token_manager = connection_banner.token_manager()
    counter = page.locator("#counter")
    increment = page.locator("#increment")
    increment.click()
    expect(counter).to_have_value("1")
    (old_sid,) = token_manager.token_to_sids[token]

    # The page loses its websocket, which the backend does not notice yet.
    old_page_side, old_backend_side = websockets[0]
    held_open.append(old_page_side)
    old_page_side.close(code=1001, reason="proxy dropped the connection")

    # The page reconnects with its token while the old socket is still linked.
    assert _poll_with_page(
        page, lambda: len(token_manager.token_to_sids.get(token, ())) == 2
    )
    new_sid = token_manager.token_to_sids[token][1]
    _assert_sockets(token_manager, redis, token, old_sid, new_sid)

    # The session is the same one: same token, same state, still usable.
    expect(counter).to_have_value("1")
    assert page.evaluate("() => sessionStorage.getItem('token')") == token
    increment.click()
    expect(counter).to_have_value("2")

    # The late disconnect of the old socket leaves the new one linked.
    old_backend_side.close()
    assert _poll_with_page(
        page, lambda: token_manager.token_to_sids.get(token) == (new_sid,)
    )
    _assert_sockets(token_manager, redis, token, new_sid)
    increment.click()
    expect(counter).to_have_value("3")
    assert page.evaluate("() => sessionStorage.getItem('token')") == token

    # A second tab with the same token shares the session.
    other_tab = page.context.new_page()
    other_tab.add_init_script(
        f"window.sessionStorage.setItem('token', {json.dumps(token)})"
    )
    other_tab.goto(connection_banner.frontend_url)
    other_counter = other_tab.locator("#counter")
    expect(other_counter).to_have_value("3")
    assert _assert_token(connection_banner, other_tab) == token
    assert _poll_with_page(
        page, lambda: len(token_manager.token_to_sids.get(token, ())) == 2
    )
    other_sid = token_manager.token_to_sids[token][1]
    _assert_sockets(token_manager, redis, token, new_sid, other_sid)

    # Each tab sees the updates the other one causes.
    other_tab.locator("#increment").click()
    expect(other_counter).to_have_value("4")
    expect(counter).to_have_value("4")
    increment.click()
    expect(counter).to_have_value("5")
    expect(other_counter).to_have_value("5")
    assert page.evaluate("() => sessionStorage.getItem('token')") == token
    assert other_tab.evaluate("() => sessionStorage.getItem('token')") == token

    # Closing one tab leaves the other one connected to the session.
    other_tab.close()
    assert _poll_with_page(
        page, lambda: token_manager.token_to_sids.get(token) == (new_sid,)
    )
    _assert_sockets(token_manager, redis, token, new_sid)
    increment.click()
    expect(counter).to_have_value("6")


def test_cloud_banner(
    connection_banner: AppHarness,
    simulate_compile_context: constants.CompileContext,
    page: Page,
):
    """Test that the connection banner is displayed when the websocket drops.

    Args:
        connection_banner: AppHarness instance.
        simulate_compile_context: Which context to set for the app.
        page: Playwright page.
    """
    assert connection_banner.app_instance is not None
    assert connection_banner.backend is not None
    assert connection_banner.frontend_url is not None
    page.goto(connection_banner.frontend_url)
    page.context.add_cookies([
        {
            "name": "backend-enabled",
            "value": "truly",
            "url": connection_banner.frontend_url,
        }
    ])
    page.reload()
    _assert_token(connection_banner, page)
    expect(page.get_by_text("This app is paused")).to_have_count(0)

    page.context.add_cookies([
        {
            "name": "backend-enabled",
            "value": "false",
            "url": connection_banner.frontend_url,
        }
    ])
    page.reload()
    if simulate_compile_context == constants.CompileContext.DEPLOY:
        expect(page.get_by_text("This app is paused")).to_be_visible()
    else:
        _assert_token(connection_banner, page)
        expect(page.get_by_text("This app is paused")).to_have_count(0)

    page.context.clear_cookies(name="backend-enabled")
    page.reload()
    _assert_token(connection_banner, page)
    expect(page.get_by_text("This app is paused")).to_have_count(0)
