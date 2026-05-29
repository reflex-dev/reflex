"""Test cases for the Starlette lifespan integration."""

import functools
from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

from .utils import SessionStorage

pytest.importorskip("fastapi")


def LifespanApp(
    mount_cached_fastapi: bool = False, mount_api_transformer: bool = False
) -> None:
    """App with lifespan tasks and context.

    Args:
        mount_cached_fastapi: Whether to mount the cached FastAPI app.
        mount_api_transformer: Whether to mount the API transformer.
    """
    import asyncio
    from contextlib import asynccontextmanager

    import reflex as rx
    from reflex.istate.manager.token import BaseStateToken

    lifespan_task_global = 0
    lifespan_context_global = 0
    raw_asyncio_task_global = 0
    connected_tokens: set[str] = set()

    @asynccontextmanager
    async def lifespan_context(app, inc: int = 1):
        global lifespan_context_global  # ty:ignore[unresolved-global]
        print(f"Lifespan context entered: {app}.")
        lifespan_context_global += inc  # ty:ignore[unresolved-reference]
        try:
            yield
        finally:
            print("Lifespan context exited.")
            lifespan_context_global += inc

    async def lifespan_task(inc: int = 1):
        global lifespan_task_global  # ty:ignore[unresolved-global]
        print("Lifespan global started.")
        try:
            while True:
                lifespan_task_global += inc
                await asyncio.sleep(0.1)
        except asyncio.CancelledError as ce:
            print(f"Lifespan global cancelled: {ce}.")
            lifespan_task_global = 0

    async def raw_asyncio_task_coro():
        global raw_asyncio_task_global  # ty:ignore[unresolved-global]
        print("Raw asyncio task started.")
        try:
            while True:
                raw_asyncio_task_global += 1
                await asyncio.sleep(0.1)
        except asyncio.CancelledError as ce:
            print(f"Raw asyncio task cancelled: {ce}.")
            raw_asyncio_task_global = 0

    @asynccontextmanager
    async def assert_register_blocked_during_lifespan(app):
        """Negative test: registering a task after lifespan has started must raise."""
        from reflex.utils.prerequisites import get_app

        reflex_app = get_app().app
        task = asyncio.create_task(raw_asyncio_task_coro(), name="raw_asyncio_task")
        try:
            reflex_app.register_lifespan_task(task)
        except RuntimeError as exc:
            print(f"Expected RuntimeError: {exc}")
        else:
            msg = "register_lifespan_task should have raised RuntimeError"
            raise AssertionError(msg)
        finally:
            task.cancel()
        yield

    class LifespanState(rx.State):
        interval: int = 100
        modify_count: int = 0

        @rx.event
        def set_interval(self, interval: int):
            self.interval = interval

        @rx.event
        def register_token(self):
            connected_tokens.add(self.router.session.client_token)

        @rx.var(cache=False)
        def task_global(self) -> int:
            return lifespan_task_global

        @rx.var(cache=False)
        def context_global(self) -> int:
            return lifespan_context_global

        @rx.var(cache=False)
        def asyncio_task_global(self) -> int:
            return raw_asyncio_task_global

        @rx.event
        def tick(self, date):
            pass

    async def modify_state_task():
        from reflex.utils.prerequisites import get_app

        reflex_app = get_app().app
        try:
            while True:
                for token in list(connected_tokens):
                    async with reflex_app.modify_state(
                        BaseStateToken(ident=token, cls=LifespanState)
                    ) as state:
                        lifespan_state = await state.get_state(LifespanState)
                        lifespan_state.modify_count += 1
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            print("modify_state_task cancelled.")

    def index():
        return rx.vstack(
            rx.text(LifespanState.task_global, id="task_global"),
            rx.text(LifespanState.context_global, id="context_global"),
            rx.text(LifespanState.modify_count, id="modify_count"),
            rx.text(LifespanState.asyncio_task_global, id="asyncio_task_global"),
            rx.button(
                rx.moment(
                    interval=LifespanState.interval, on_change=LifespanState.tick
                ),
                on_click=LifespanState.set_interval(
                    rx.cond(LifespanState.interval, 0, 100)
                ),
                id="toggle-tick",
            ),
            on_mount=LifespanState.register_token,
        )

    from fastapi import FastAPI

    app = rx.App(api_transformer=FastAPI() if mount_api_transformer else None)

    if mount_cached_fastapi:
        assert app._api is not None

    app.register_lifespan_task(lifespan_task)
    app.register_lifespan_task(lifespan_context, inc=2)
    app.register_lifespan_task(raw_asyncio_task_coro)
    app.register_lifespan_task(assert_register_blocked_during_lifespan)
    app.register_lifespan_task(modify_state_task)
    app.add_page(index)


@pytest.fixture(
    scope="session",
    params=[False, True],
    ids=["no_api_transformer", "mount_api_transformer"],
)
def mount_api_transformer(request: pytest.FixtureRequest) -> bool:
    """Whether to use api_transformer in the app.

    Args:
        request: pytest fixture request object

    Returns:
        bool: Whether to use api_transformer
    """
    return request.param


@pytest.fixture(
    scope="session", params=[False, True], ids=["no_fastapi", "mount_cached_fastapi"]
)
def mount_cached_fastapi(request: pytest.FixtureRequest) -> bool:
    """Whether to use cached FastAPI in the app (app.api).

    Args:
        request: pytest fixture request object

    Returns:
        Whether to use cached FastAPI
    """
    return request.param


@pytest.fixture(scope="session")
def lifespan_app(
    tmp_path_factory: pytest.TempPathFactory,
    app_harness_env: type[AppHarness],
    mount_api_transformer: bool,
    mount_cached_fastapi: bool,
) -> Generator[AppHarness, None, None]:
    """Start LifespanApp app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture
        app_harness_env: AppHarness environment
        mount_api_transformer: Whether to mount the API transformer.
        mount_cached_fastapi: Whether to mount the cached FastAPI app.

    Yields:
        running AppHarness instance
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("lifespan_app"),
        app_source=functools.partial(
            LifespanApp,
            mount_cached_fastapi=mount_cached_fastapi,
            mount_api_transformer=mount_api_transformer,
        ),
        app_name=f"lifespanapp_fastapi{mount_cached_fastapi}_transformer{mount_api_transformer}",
    ) as harness:
        yield harness


def test_lifespan_modify_state(lifespan_app: AppHarness):
    """Test that a lifespan task can use app.modify_state to push state updates.

    Args:
        lifespan_app: harness for LifespanApp app
    """
    assert lifespan_app.app_module is not None, "app module is not found"
    assert lifespan_app.app_instance is not None, "app is not running"
    driver = lifespan_app.frontend()

    ss = SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    modify_count = driver.find_element(By.ID, "modify_count")

    # Wait for modify_count to become non-zero (lifespan task is pushing updates)
    assert lifespan_app.poll_for_content(modify_count, exp_not_equal="0")

    # Verify it continues to increase
    first_value = modify_count.text
    next_value = lifespan_app.poll_for_content(modify_count, exp_not_equal=first_value)
    assert int(next_value) > int(first_value)


def test_lifespan_raw_asyncio_task(lifespan_app: AppHarness):
    """Test that a coroutine function registered as a lifespan task runs as an asyncio.Task.

    Args:
        lifespan_app: harness for LifespanApp app
    """
    assert lifespan_app.app_module is not None, "app module is not found"
    assert lifespan_app.app_instance is not None, "app is not running"
    driver = lifespan_app.frontend()

    ss = SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    asyncio_task_global = driver.find_element(By.ID, "asyncio_task_global")

    # Wait for asyncio_task_global to become non-zero
    assert lifespan_app.poll_for_content(asyncio_task_global, exp_not_equal="0")

    # Verify it continues to increase
    first_value = asyncio_task_global.text
    next_value = lifespan_app.poll_for_content(
        asyncio_task_global, exp_not_equal=first_value
    )
    assert int(next_value) > int(first_value)
    assert lifespan_app.app_module.raw_asyncio_task_global > 0


# --- test_lifespan MUST be the last test in this file. ---
# It shuts down the backend and asserts cancellation of lifespan tasks.
# The lifespan_app fixture is session-scoped (expensive to rebuild), so all
# other tests that need a running backend must be defined ABOVE this point.


def test_lifespan(lifespan_app: AppHarness):
    """Test the lifespan integration.

    Args:
        lifespan_app: harness for LifespanApp app
    """
    assert lifespan_app.app_module is not None, "app module is not found"
    assert lifespan_app.app_instance is not None, "app is not running"
    driver = lifespan_app.frontend()

    ss = SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    context_global = driver.find_element(By.ID, "context_global")
    task_global = driver.find_element(By.ID, "task_global")

    assert lifespan_app.poll_for_content(context_global, exp_not_equal="0") == "2"
    assert lifespan_app.app_module.lifespan_context_global == 2

    original_task_global_text = task_global.text
    original_task_global_value = int(original_task_global_text)
    lifespan_app.poll_for_content(task_global, exp_not_equal=original_task_global_text)
    driver.find_element(By.ID, "toggle-tick").click()  # avoid teardown errors
    assert lifespan_app.app_module.lifespan_task_global > original_task_global_value
    assert int(task_global.text) > original_task_global_value

    # Kill the backend
    assert lifespan_app.backend is not None
    lifespan_app.backend.should_exit = True
    if lifespan_app.backend_thread is not None:
        lifespan_app.backend_thread.join()

    # Check that the lifespan tasks have been cancelled
    assert lifespan_app.app_module.lifespan_task_global == 0
    assert lifespan_app.app_module.lifespan_context_global == 4
    assert lifespan_app.app_module.raw_asyncio_task_global == 0


# --- Do NOT add new test cases below this line. ---
# test_lifespan (above) kills the backend; any test defined after it will
# find the harness in a stopped state and fail.
