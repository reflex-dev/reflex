"""Test @rx.event(background=True) task functionality."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def BackgroundTask():
    """Test that background tasks work as expected."""
    import asyncio

    import pytest

    import reflex as rx
    from reflex.state import ImmutableStateError

    class State(rx.State):
        counter: int = 0
        _task_id: int = 0
        iterations: rx.Field[int] = rx.field(10)

        @rx.event
        def set_iterations(self, value: str):
            self.iterations = int(value)

        @rx.var
        async def counter_async_cv(self) -> int:
            """This exists solely as an integration test for background tasks triggering async var updates.

            Returns:
                The current value of the counter.
            """
            return self.counter

        @rx.event(background=True)
        async def handle_event(self):
            async with self:
                self._task_id += 1
            for _ix in range(int(self.iterations)):
                async with self:
                    self.counter += 1
                await asyncio.sleep(0.005)

        @rx.event(background=True)
        async def handle_event_yield_only(self):
            async with self:
                self._task_id += 1
            for ix in range(int(self.iterations)):
                if ix % 2 == 0:
                    yield State.increment_arbitrary(1)
                else:
                    yield State.increment()
                await asyncio.sleep(0.005)

        @rx.event
        def increment(self):
            self.counter += 1

        @rx.event(background=True)
        async def increment_arbitrary(self, amount: int):
            async with self:
                self.counter += int(amount)

        @rx.event
        def reset_counter(self):
            self.counter = 0

        @rx.event
        async def blocking_pause(self):
            await asyncio.sleep(0.02)

        @rx.event(background=True)
        async def non_blocking_pause(self):
            await asyncio.sleep(0.02)

        async def racy_task(self):
            async with self:
                self._task_id += 1
            for _ix in range(int(self.iterations)):
                async with self:
                    self.counter += 1
                await asyncio.sleep(0.005)

        @rx.event(background=True)
        async def handle_racy_event(self):
            await asyncio.gather(
                self.racy_task(), self.racy_task(), self.racy_task(), self.racy_task()
            )

        @rx.event(background=True)
        async def nested_async_with_self(self):
            async with self:
                self.counter += 1
                with pytest.raises(ImmutableStateError):
                    async with self:
                        self.counter += 1

        async def triple_count(self):
            third_state = await self.get_state(ThirdState)
            await third_state._triple_count()

        @rx.event(background=True)
        async def yield_in_async_with_self(self):
            async with self:
                self.counter += 1
                yield
                self.counter += 1

        @rx.event
        async def disconnect_reconnect(self):
            self.counter += 1
            yield rx.call_script("socket.disconnect()")
            await asyncio.sleep(0.5)
            self.counter += 1

        @rx.event(background=True)
        async def disconnect_reconnect_background(self):
            async with self:
                self.counter += 1
            yield rx.call_script("socket.disconnect()")
            await asyncio.sleep(0.5)
            async with self:
                self.counter += 1

    class OtherState(rx.State):
        @rx.event(background=True)
        async def get_other_state(self):
            async with self:
                state = await self.get_state(State)
                state.counter += 1
                await state.triple_count()
            with pytest.raises(ImmutableStateError):
                await state.triple_count()
            with pytest.raises(ImmutableStateError):
                state.counter += 1
            async with state:
                state.counter += 1
                await state.triple_count()

    class ThirdState(rx.State):
        async def _triple_count(self):
            state = await self.get_state(State)
            state.counter *= 3

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                id="token", value=State.router.session.client_token, is_read_only=True
            ),
            rx.input(
                id="sid", value=State.router.session.session_id, is_read_only=True
            ),
            rx.hstack(
                rx.heading(State.counter, id="counter"),
                rx.text(State.counter_async_cv, size="1", id="counter-async-cv"),
            ),
            rx.input(
                id="iterations",
                placeholder="Iterations",
                value=State.iterations.to_string(),
                on_change=State.set_iterations,
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
            rx.button(
                "Racy Increment (x4)",
                on_click=State.handle_racy_event,
                id="racy-increment",
            ),
            rx.button(
                "Nested Async with Self",
                on_click=State.nested_async_with_self,
                id="nested-async-with-self",
            ),
            rx.button(
                "Increment from OtherState",
                on_click=OtherState.get_other_state,
                id="increment-from-other-state",
            ),
            rx.button(
                "Yield in Async with Self",
                on_click=State.yield_in_async_with_self,
                id="yield-in-async-with-self",
            ),
            rx.button(
                "Disconnect / Reconnect",
                on_click=State.disconnect_reconnect_background,
                id="disconnect-reconnect",
            ),
            rx.button(
                "Disconnect / Reconnect Background",
                on_click=State.disconnect_reconnect_background,
                id="disconnect-reconnect-background",
            ),
            rx.button("Reset", on_click=State.reset_counter, id="reset"),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def background_task(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start BackgroundTask app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("background_task"),
        app_source=BackgroundTask,
    ) as harness:
        yield harness


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


@pytest.fixture
def token(background_task: AppHarness, driver: WebDriver) -> str:
    """Get a function that returns the active token.

    Args:
        background_task: harness for BackgroundTask app.
        driver: WebDriver instance.

    Returns:
        The token for the connected client
    """
    assert background_task.app_instance is not None

    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )

    # wait for the backend connection to send the token
    token = background_task.poll_for_value(token_input, timeout=DEFAULT_TIMEOUT * 2)
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
    racy_increment_button = driver.find_element(By.ID, "racy-increment")
    driver.find_element(By.ID, "reset")

    # get a reference to the counter
    counter = driver.find_element(By.ID, "counter")
    counter_async_cv = driver.find_element(By.ID, "counter-async-cv")

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
    racy_increment_button.click()
    non_blocking_pause_button.click()
    yield_increment_button.click()
    blocking_pause_button.click()
    yield_increment_button.click()
    for _ in range(10):
        increment_button.click()
    yield_increment_button.click()
    blocking_pause_button.click()
    AppHarness.expect(lambda: counter.text == "620", timeout=40)
    AppHarness.expect(lambda: counter_async_cv.text == "620", timeout=40)
    # all tasks should have exited and cleaned up
    AppHarness.expect(
        lambda: not background_task.app_instance._background_tasks  # pyright: ignore [reportOptionalMemberAccess]
    )


def test_nested_async_with_self(
    background_task: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that nested async with self in the same coroutine raises Exception.

    Args:
        background_task: harness for BackgroundTask app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    nested_async_with_self_button = driver.find_element(By.ID, "nested-async-with-self")
    increment_button = driver.find_element(By.ID, "increment")

    # get a reference to the counter
    counter = driver.find_element(By.ID, "counter")
    AppHarness.expect(lambda: counter.text == "0", timeout=5)

    nested_async_with_self_button.click()
    AppHarness.expect(lambda: counter.text == "1", timeout=5)

    increment_button.click()
    AppHarness.expect(lambda: counter.text == "2", timeout=5)


def test_get_state(
    background_task: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that get_state returns a state bound to the correct StateProxy.

    Args:
        background_task: harness for BackgroundTask app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    other_state_button = driver.find_element(By.ID, "increment-from-other-state")
    increment_button = driver.find_element(By.ID, "increment")

    # get a reference to the counter
    counter = driver.find_element(By.ID, "counter")
    AppHarness.expect(lambda: counter.text == "0", timeout=5)

    other_state_button.click()
    AppHarness.expect(lambda: counter.text == "12", timeout=5)

    increment_button.click()
    AppHarness.expect(lambda: counter.text == "13", timeout=5)


def test_yield_in_async_with_self(
    background_task: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that yielding inside async with self does not disable mutability.

    Args:
        background_task: harness for BackgroundTask app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    yield_in_async_with_self_button = driver.find_element(
        By.ID, "yield-in-async-with-self"
    )

    # get a reference to the counter
    counter = driver.find_element(By.ID, "counter")
    AppHarness.expect(lambda: counter.text == "0", timeout=5)

    yield_in_async_with_self_button.click()
    AppHarness.expect(lambda: counter.text == "2", timeout=5)


@pytest.mark.parametrize(
    "button_id",
    [
        "disconnect-reconnect",
        "disconnect-reconnect-background",
    ],
)
def test_disconnect_reconnect(
    background_task: AppHarness,
    driver: WebDriver,
    token: str,
    button_id: str,
):
    """Test that disconnecting and reconnecting works as expected.

    Args:
        background_task: harness for BackgroundTask app.
        driver: WebDriver instance.
        token: The token for the connected client.
        button_id: The ID of the button to click.
    """
    counter = driver.find_element(By.ID, "counter")
    button = driver.find_element(By.ID, button_id)
    increment_button = driver.find_element(By.ID, "increment")
    sid_input = driver.find_element(By.ID, "sid")
    sid = background_task.poll_for_value(sid_input, timeout=5)
    assert sid is not None

    AppHarness.expect(lambda: counter.text == "0", timeout=5)
    button.click()
    AppHarness.expect(lambda: counter.text == "1", timeout=5)
    increment_button.click()
    # should get a new sid after the reconnect
    assert (
        background_task.poll_for_value(sid_input, timeout=5, exp_not_equal=sid) != sid
    )
    # Final update should come through on the new websocket connection
    AppHarness.expect(lambda: counter.text == "3", timeout=5)
