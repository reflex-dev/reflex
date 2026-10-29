"""Test @rx.event(background=True) task functionality."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


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

        @rx.event(background=True)
        async def fast_yielding(self):
            for _ in range(1000):
                yield State.increment()

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
                "Disconnect / Reconnect Background",
                on_click=State.disconnect_reconnect_background,
                id="disconnect-reconnect-background",
            ),
            rx.button(
                "Fast Yielding",
                on_click=State.fast_yielding,
                id="fast-yielding",
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
def background_page(background_task: AppHarness, page: Page) -> Page:
    """Open the app and wait for its client connection.

    Returns:
        The connected Playwright page.
    """
    assert background_task.frontend_url is not None
    page.goto(background_task.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    return page


@pytest.fixture
def token(background_page: Page) -> str:
    """Get a function that returns the active token.

    Args:
        background_page: Playwright page.

    Returns:
        The token for the connected client
    """
    return background_page.locator("#token").input_value()


def test_background_task(
    background_task: AppHarness,
    background_page: Page,
    token: str,
):
    """Test that background tasks work as expected.

    Args:
        background_task: harness for BackgroundTask app.
        background_page: Playwright page.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    delayed_increment_button = background_page.locator("#delayed-increment")
    yield_increment_button = background_page.locator("#yield-increment")
    increment_button = background_page.locator("#increment")
    blocking_pause_button = background_page.locator("#blocking-pause")
    non_blocking_pause_button = background_page.locator("#non-blocking-pause")
    racy_increment_button = background_page.locator("#racy-increment")
    expect(background_page.locator("#reset")).to_be_visible()

    # get a reference to the counter
    counter = background_page.locator("#counter")
    counter_async_cv = background_page.locator("#counter-async-cv")

    # get a reference to the iterations input
    iterations_input = background_page.locator("#iterations")

    # kick off background tasks
    iterations_input.fill("50")
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
    expect(counter).to_have_text("620", timeout=40_000)
    expect(counter_async_cv).to_have_text("620", timeout=40_000)
    # all tasks should have exited and cleaned up
    AppHarness.expect(
        lambda: not background_task.app_instance.event_processor._tasks  # pyright: ignore [reportOptionalMemberAccess]
    )


def test_nested_async_with_self(
    background_task: AppHarness,
    background_page: Page,
    token: str,
):
    """Test that nested async with self in the same coroutine raises Exception.

    Args:
        background_task: harness for BackgroundTask app.
        background_page: Playwright page.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    nested_async_with_self_button = background_page.locator("#nested-async-with-self")
    increment_button = background_page.locator("#increment")

    # get a reference to the counter
    counter = background_page.locator("#counter")
    expect(counter).to_have_text("0")

    nested_async_with_self_button.click()
    expect(counter).to_have_text("1")

    increment_button.click()
    expect(counter).to_have_text("2")


def test_get_state(
    background_task: AppHarness,
    background_page: Page,
    token: str,
):
    """Test that get_state returns a state bound to the correct StateProxy.

    Args:
        background_task: harness for BackgroundTask app.
        background_page: Playwright page.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    other_state_button = background_page.locator("#increment-from-other-state")
    increment_button = background_page.locator("#increment")

    # get a reference to the counter
    counter = background_page.locator("#counter")
    expect(counter).to_have_text("0")

    other_state_button.click()
    expect(counter).to_have_text("12")

    increment_button.click()
    expect(counter).to_have_text("13")


def test_yield_in_async_with_self(
    background_task: AppHarness,
    background_page: Page,
    token: str,
):
    """Test that yielding inside async with self does not disable mutability.

    Args:
        background_task: harness for BackgroundTask app.
        background_page: Playwright page.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    yield_in_async_with_self_button = background_page.locator(
        "#yield-in-async-with-self"
    )

    # get a reference to the counter
    counter = background_page.locator("#counter")
    expect(counter).to_have_text("0")

    yield_in_async_with_self_button.click()
    expect(counter).to_have_text("2")


@pytest.mark.parametrize(
    "button_id",
    [
        "disconnect-reconnect-background",
    ],
)
def test_disconnect_reconnect(
    background_task: AppHarness,
    background_page: Page,
    token: str,
    button_id: str,
):
    """Test that disconnecting and reconnecting works as expected.

    Args:
        background_task: harness for BackgroundTask app.
        background_page: Playwright page.
        token: The token for the connected client.
        button_id: The ID of the button to click.
    """
    counter = background_page.locator("#counter")
    button = background_page.locator(f"#{button_id}")
    increment_button = background_page.locator("#increment")
    sid_input = background_page.locator("#sid")
    sid = sid_input.input_value()

    expect(counter).to_have_text("0")
    button.click()
    expect(counter).to_have_text("1")
    increment_button.click()
    # should get a new sid after the reconnect
    expect(sid_input).not_to_have_value(sid, timeout=5_000)
    # Final update should come through on the new websocket connection
    expect(counter).to_have_text("3")


def test_fast_yielding(
    background_task: AppHarness,
    background_page: Page,
    token: str,
) -> None:
    """Test that fast yielding works as expected.

    Args:
        background_task: harness for BackgroundTask app.
        background_page: Playwright page.
        token: The token for the connected client.
    """
    assert background_task.app_instance is not None

    # get a reference to all buttons
    fast_yielding_button = background_page.locator("#fast-yielding")

    # get a reference to the counter
    counter = background_page.locator("#counter")
    expect(counter).to_have_text("0")

    fast_yielding_button.click()
    expect(counter).to_have_text("1000", timeout=50_000)
