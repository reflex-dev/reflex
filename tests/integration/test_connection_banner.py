"""Test case for displaying the connection banner when the websocket drops."""

import contextlib
import pickle
from collections.abc import Generator, Iterator

import pytest
from playwright.sync_api import Page, expect
from redis import Redis
from reflex_base import constants

from reflex.environment import environment
from reflex.istate.manager.redis import StateManagerRedis
from reflex.testing import AppHarness
from reflex.utils.token_manager import RedisTokenManager, SocketRecord

from .utils import SessionStorage


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
    scope="module",
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


@pytest.fixture(scope="module")
def connection_banner(
    tmp_path_factory: pytest.TempPathFactory,
    simulate_compile_context: constants.CompileContext,
) -> Generator[AppHarness, None, None]:
    """Start ConnectionBanner app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture
        simulate_compile_context: Which context to run the app with.

    Yields:
        running AppHarness instance
    """
    environment.REFLEX_COMPILE_CONTEXT.set(simulate_compile_context)

    app_name = (
        "connection_banner_reflex_cloud"
        if simulate_compile_context == constants.CompileContext.DEPLOY
        else "connection_banner"
    )
    with AppHarness.create(
        root=tmp_path_factory.mktemp(app_name),
        app_source=ConnectionBanner,
        app_name=app_name,
    ) as harness:
        yield harness


@contextlib.contextmanager
def browser_offline(page: Page) -> Iterator[None]:
    """Context manager that takes the browser offline and restores it on exit.

    Args:
        page: Playwright page whose context will be toggled offline.

    Yields:
        None
    """
    page.context.set_offline(True)
    try:
        yield
    finally:
        page.context.set_offline(False)


CONNECTION_ERROR_XPATH = "xpath=//*[ contains(text(), 'Cannot connect to server') ]"


def has_error_modal(page: Page) -> bool:
    """Check if the connection error modal is displayed.

    Args:
        page: Playwright page to query.

    Returns:
        True if the modal is displayed, False otherwise.
    """
    return page.locator(CONNECTION_ERROR_XPATH).count() > 0


def has_cloud_banner(page: Page) -> bool:
    """Check if the cloud banner is displayed.

    Args:
        page: Playwright page to query.

    Returns:
        True if the banner is displayed, False otherwise.
    """
    return (
        page.locator("xpath=//*[ contains(text(), 'This app is paused') ]").count() > 0
    )


def _assert_token(connection_banner: AppHarness, page: Page) -> str:
    """Poll for backend to be up.

    Args:
        connection_banner: AppHarness instance.
        page: Playwright page.

    Returns:
        The token if found, raises an assertion error otherwise.
    """
    ss = SessionStorage(page)
    assert connection_banner._poll_for(lambda: ss.get("token") is not None), (
        "token not found"
    )
    token = ss.get("token")
    assert token is not None
    return token


@pytest.fixture
def redis(
    connection_banner: AppHarness,
) -> Generator[Redis | None]:
    """Get a synchronous Redis client when the app is using the Redis state manager.

    Args:
        connection_banner: AppHarness instance.

    Yields:
        A sync Redis client, or None if the StateManager is not Redis.
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
    AppHarness.expect(lambda: not has_error_modal(page))

    # Check that the token association was established.
    app_token_manager = connection_banner.token_manager()
    assert token in app_token_manager.token_to_sid
    sid_before = app_token_manager.token_to_sid[token]
    if redis is not None:
        assert isinstance(app_token_manager, RedisTokenManager)
        assert redis.get(app_token_manager._get_redis_key(token)) == pickle.dumps(
            SocketRecord(instance_id=app_token_manager.instance_id, sid=sid_before)
        )

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
        AppHarness.expect(lambda: has_error_modal(page))

        # The token association should be removed once the websocket closes on the server.
        assert connection_banner._poll_for(
            lambda: token not in app_token_manager.token_to_sid
        )
        if redis is not None:
            assert isinstance(app_token_manager, RedisTokenManager)
            assert redis.get(app_token_manager._get_redis_key(token)) is None

        # Increment the counter while disconnected
        increment_button.click()
        expect(counter_element).to_have_value("1")

    # Banner should be gone now (network restored on context manager exit)
    AppHarness.expect(lambda: not has_error_modal(page))

    # After reconnecting, the token association should be re-established.
    app_token_manager = connection_banner.token_manager()
    # Make sure the new connection has a different websocket sid.
    sid_after = app_token_manager.token_to_sid[token]
    assert sid_before != sid_after
    if redis is not None:
        assert isinstance(app_token_manager, RedisTokenManager)
        assert redis.get(app_token_manager._get_redis_key(token)) == pickle.dumps(
            SocketRecord(instance_id=app_token_manager.instance_id, sid=sid_after)
        )

    # Count should have incremented after coming back up
    expect(counter_element).to_have_value("2")


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
    AppHarness.expect(lambda: not has_cloud_banner(page))

    page.context.add_cookies([
        {
            "name": "backend-enabled",
            "value": "false",
            "url": connection_banner.frontend_url,
        }
    ])
    page.reload()
    if simulate_compile_context == constants.CompileContext.DEPLOY:
        AppHarness.expect(lambda: has_cloud_banner(page))
    else:
        _assert_token(connection_banner, page)
        AppHarness.expect(lambda: not has_cloud_banner(page))

    page.context.clear_cookies(name="backend-enabled")
    page.reload()
    _assert_token(connection_banner, page)
    AppHarness.expect(lambda: not has_cloud_banner(page))
