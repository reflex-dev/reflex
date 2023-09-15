"""Test @rx.background task functionality."""

import os
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver


def BackgroundTask():
    """Test that background tasks work as expected."""
    import asyncio

    import reflex as rx

    class State(rx.State):
        counter: int = 0
        _task_id: int = 0
        iterations: int = 10

        @rx.background
        async def handle_event(self):
            async with self:
                self._task_id += 1
            for _ix in range(int(self.iterations)):
                async with self:
                    self.counter += 1
                await asyncio.sleep(0.005)

        @rx.background
        async def handle_event_yield_only(self):
            async with self:
                self._task_id += 1
            for ix in range(int(self.iterations)):
                if ix % 2 == 0:
                    yield State.increment_arbitrary(1)  # type: ignore
                else:
                    yield State.increment()  # type: ignore
                await asyncio.sleep(0.005)

        def increment(self):
            self.counter += 1

        @rx.background
        async def increment_arbitrary(self, amount: int):
            async with self:
                self.counter += int(amount)

        def reset_counter(self):
            self.counter = 0

        async def blocking_pause(self):
            await asyncio.sleep(0.02)

        @rx.background
        async def non_blocking_pause(self):
            await asyncio.sleep(0.02)

        @rx.cached_var
        def token(self) -> str:
            return self.get_token()

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(id="token", value=State.token, is_read_only=True),
            rx.heading(State.counter, id="counter"),
            rx.input(
                id="iterations",
                placeholder="Iterations",
                value=State.iterations.to_string(),  # type: ignore
                on_change=State.set_iterations,  # type: ignore
            ),
            rx.button(
                "Delayed Increment",
                on_click=State.handle_event,
                id="delayed-increment",
            ),
            rx.button(
                "Yield Increment",
                on_click=State.handle_event_yield_only,
                id="yield-increment",
            ),
            rx.button("Increment 1", on_click=State.increment, id="increment"),
            rx.button(
                "Blocking Pause",
                on_click=State.blocking_pause,
                id="blocking-pause",
            ),
            rx.button(
                "Non-Blocking Pause",
                on_click=State.non_blocking_pause,
                id="non-blocking-pause",
            ),
            rx.button("Reset", on_click=State.reset_counter, id="reset"),
        )

    app = rx.App(state=State)
    app.add_page(index)
    app.compile()


@pytest.fixture(scope="session", params=[True, False], ids=["redis", "in_process"])
def background_task(
    request,
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start BackgroundTask app at tmp_path via AppHarness.

    Args:
        request: the pytest fixturerequest object
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    orig_redis_url = os.environ.get("REDIS_URL")
    if request.param:
        if not orig_redis_url:
            pytest.skip("REDIS_URL not set")
    else:
        os.environ.pop("REDIS_URL", "")

    with AppHarness.create(
        root=tmp_path_factory.mktemp(f"background_task"),
        app_source=BackgroundTask,  # type: ignore
    ) as harness:
        yield harness

    if orig_redis_url is not None:
        os.environ["REDIS_URL"] = orig_redis_url


@pytest.fixture
def driver(background_task: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the background_task app.

    Args:
        background_task: harness for BackgroundTask app

    Yields:
        WebDriver instance.
    """
    assert background_task.app_instance is not None, "app is not running"
    driver = background_task.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture()
def token(background_task: AppHarness, driver: WebDriver) -> str:
    """Get a function that returns the active token.

    Args:
        background_task: harness for BackgroundTask app.
        driver: WebDriver instance.

    Returns:
        The token for the connected client
    """
    assert background_task.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = background_task.poll_for_value(token_input)
    assert token is not None

    return token


def test_background_task(
    background_task: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that background tasks work as expected.

    Args:
        background_task: harness for BackgroundTask app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    delayed_increment_button = driver.find_element(By.ID, "delayed-increment")
    yield_increment_button = driver.find_element(By.ID, "yield-increment")
    increment_button = driver.find_element(By.ID, "increment")
    blocking_pause_button = driver.find_element(By.ID, "blocking-pause")
    non_blocking_pause_button = driver.find_element(By.ID, "non-blocking-pause")
    driver.find_element(By.ID, "reset")

    # get a reference to the counter
    counter = driver.find_element(By.ID, "counter")

    # get a reference to the iterations input
    iterations_input = driver.find_element(By.ID, "iterations")

    # kick off background tasks
    iterations_input.clear()
    iterations_input.send_keys("50")
    delayed_increment_button.click()
    blocking_pause_button.click()
    delayed_increment_button.click()
    for _ in range(10):
        increment_button.click()
    blocking_pause_button.click()
    delayed_increment_button.click()
    delayed_increment_button.click()
    yield_increment_button.click()
    non_blocking_pause_button.click()
    yield_increment_button.click()
    blocking_pause_button.click()
    yield_increment_button.click()
    for _ in range(10):
        increment_button.click()
    yield_increment_button.click()
    blocking_pause_button.click()
    assert background_task._poll_for(lambda: counter.text == "420", timeout=40)
    # all tasks should have exited and cleaned up
    assert background_task._poll_for(
        lambda: not background_task.app_instance.background_tasks  # type: ignore
    )
