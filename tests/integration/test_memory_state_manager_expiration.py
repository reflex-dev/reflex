"""Integration tests for in-memory state expiration."""

import time
from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from reflex.istate.manager.memory import StateManagerMemory
from reflex.testing import AppHarness


def MemoryExpirationApp():
    """Reflex app that exposes state expiration through a simple counter UI."""
    import asyncio

    import reflex as rx

    class State(rx.State):
        counter: int = 0

        @rx.event
        def increment(self):
            self.counter += 1

        @rx.event(background=True)
        async def delayed_update(self):
            await asyncio.sleep(2)
            async with self:
                self.counter = 100

    class ChildState(State):
        child_counter: int = 0

        @rx.event
        def set_values(self):
            self.counter = 11
            self.child_counter = 13

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                id="token",
                value=State.router.session.client_token,
                is_read_only=True,
            ),
            rx.text(State.counter, id="counter"),
            rx.text(ChildState.child_counter, id="child-counter"),
            rx.button("Increment", id="increment", on_click=State.increment),
            rx.button("Set values", id="set-values", on_click=ChildState.set_values),
            rx.button(
                "Delayed update",
                id="delayed-update",
                on_click=State.delayed_update,
            ),
        )


@pytest.fixture
def memory_expiration_app(
    app_harness_env: type[AppHarness],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start a memory-backed app with a short expiration window.

    Yields:
        A running app harness configured to use StateManagerMemory.
    """
    monkeypatch.setenv("REFLEX_STATE_MANAGER_MODE", "memory")
    # Memory expiration reuses the shared token_expiration config field.
    monkeypatch.setenv("REFLEX_REDIS_TOKEN_EXPIRATION", "1")

    with app_harness_env.create(
        root=tmp_path_factory.mktemp("memory_expiration_app"),
        app_name=f"memory_expiration_{app_harness_env.__name__.lower()}",
        app_source=MemoryExpirationApp,
    ) as harness:
        assert isinstance(
            getattr(harness.app_instance, "state_manager", None), StateManagerMemory
        )
        yield harness


@pytest.fixture
def driver(memory_expiration_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Open the memory expiration app in a browser.

    Yields:
        A webdriver instance pointed at the running app.
    """
    assert memory_expiration_app.app_instance is not None, "app is not running"
    driver = memory_expiration_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def test_memory_state_manager_expires_state_end_to_end(
    memory_expiration_app: AppHarness,
    driver: WebDriver,
):
    """An idle in-memory state should expire and reset on the next event."""
    app_instance = memory_expiration_app.app_instance
    assert app_instance is not None

    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )
    token = memory_expiration_app.poll_for_value(token_input)
    assert token is not None

    counter = driver.find_element(By.ID, "counter")
    increment = driver.find_element(By.ID, "increment")
    app_state_manager = app_instance.state_manager
    assert isinstance(app_state_manager, StateManagerMemory)

    AppHarness.expect(lambda: counter.text == "0")

    increment.click()
    AppHarness.expect(lambda: counter.text == "1")

    increment.click()
    AppHarness.expect(lambda: counter.text == "2")

    AppHarness.expect(lambda: token in app_state_manager.states)
    AppHarness.expect(lambda: token not in app_state_manager.states, timeout=5)

    increment.click()
    AppHarness.expect(lambda: counter.text == "1")
    assert token_input.get_attribute("value") == token


def test_memory_state_manager_delays_expiration_after_use_end_to_end(
    memory_expiration_app: AppHarness,
    driver: WebDriver,
):
    """Using a token should start a fresh expiration window from the last use."""
    app_instance = memory_expiration_app.app_instance
    assert app_instance is not None

    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )
    token = memory_expiration_app.poll_for_value(token_input)
    assert token is not None

    counter = driver.find_element(By.ID, "counter")
    increment = driver.find_element(By.ID, "increment")
    app_state_manager = app_instance.state_manager
    assert isinstance(app_state_manager, StateManagerMemory)

    AppHarness.expect(lambda: counter.text == "0")

    increment.click()
    AppHarness.expect(lambda: counter.text == "1")
    AppHarness.expect(lambda: token in app_state_manager.states)

    time.sleep(0.6)
    increment.click()
    AppHarness.expect(lambda: counter.text == "2")
    AppHarness.expect(lambda: token in app_state_manager.states)

    time.sleep(0.6)
    increment.click()
    AppHarness.expect(lambda: counter.text == "3")
    AppHarness.expect(lambda: token in app_state_manager.states)

    time.sleep(0.6)
    assert token in app_state_manager.states
    assert counter.text == "3"

    AppHarness.expect(lambda: token not in app_state_manager.states, timeout=5)

    increment.click()
    AppHarness.expect(lambda: counter.text == "1")
    assert token_input.get_attribute("value") == token



def test_background_task_refreshes_recreated_substate(
    memory_expiration_app: AppHarness,
    driver: WebDriver,
):
    """A delayed background update must send defaults for expired substates."""
    counter = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "counter")
    )
    child_counter = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "child-counter")
    )
    driver.find_element(By.ID, "set-values").click()
    AppHarness.expect(lambda: counter.text == "11")
    AppHarness.expect(lambda: child_counter.text == "13")

    driver.find_element(By.ID, "delayed-update").click()
    AppHarness.expect(lambda: counter.text == "100", timeout=10)
    AppHarness.expect(lambda: child_counter.text == "0", timeout=10)
