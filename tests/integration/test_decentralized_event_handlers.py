"""Test decentralized event handlers functionality."""

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver


def DecentralizedEventHandlers():
    """Test that decentralized event handlers work as expected."""
    import reflex as rx

    class TestState(rx.State):
        count: int = 0
        value: int = 0

        @rx.event
        def increment(self):
            """Increment the counter."""
            self.count += 1

    @rx.event
    def on_load(state: TestState):
        """Event handler for loading the state.

        Args:
            state: The state to modify.
        """
        state.count = 10

    @rx.event
    def reset_count(state: TestState):
        """Event handler for resetting the count.

        Args:
            state: The state to modify.
        """
        state.count = 0

    @rx.event
    def set_value(state: TestState, value: str):
        """Set the value with a parameter.

        Args:
            state: The state to modify.
            value: The value to set.
        """
        state.value = int(value)

    def index():
        return rx.vstack(
            rx.heading(TestState.count, id="counter"),
            rx.heading(TestState.value, id="value"),
            rx.button("Increment", on_click=TestState.increment, id="increment"),
            rx.button("Reset", on_click=reset_count, id="reset"),
            rx.button("Set Value", on_click=set_value("42"), id="set-value"),
            rx.text("Loaded", on_mount=on_load, id="loaded"),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def decentralized_handlers(
    tmp_path_factory,
):
    """Start DecentralizedEventHandlers app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("decentralized_handlers"),
        app_source=DecentralizedEventHandlers,
    ) as harness:
        yield harness


@pytest.fixture
def driver(decentralized_handlers: AppHarness):
    """Get an instance of the browser open to the app.

    Args:
        decentralized_handlers: harness for DecentralizedEventHandlers app

    Yields:
        WebDriver instance.
    """
    assert decentralized_handlers.app_instance is not None, "app is not running"
    driver = decentralized_handlers.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def test_decentralized_event_handlers(
    decentralized_handlers: AppHarness,
    driver: WebDriver,
):
    """Test that decentralized event handlers work as expected.

    Args:
        decentralized_handlers: harness for DecentralizedEventHandlers app
        driver: WebDriver instance
    """
    assert decentralized_handlers.app_instance is not None

    counter = driver.find_element(By.ID, "counter")
    value = driver.find_element(By.ID, "value")
    increment_button = driver.find_element(By.ID, "increment")
    reset_button = driver.find_element(By.ID, "reset")
    set_value_button = driver.find_element(By.ID, "set-value")

    assert decentralized_handlers._poll_for(lambda: counter.text == "10", timeout=5)
    assert value.text == "0"

    increment_button.click()
    assert decentralized_handlers._poll_for(lambda: counter.text == "11", timeout=5)

    reset_button.click()
    assert decentralized_handlers._poll_for(lambda: counter.text == "0", timeout=5)

    set_value_button.click()
    assert decentralized_handlers._poll_for(lambda: value.text == "42", timeout=5)
