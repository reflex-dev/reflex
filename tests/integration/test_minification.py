"""Integration tests for state and event handler minification."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from selenium.webdriver.common.by import By

from reflex.minify import MINIFY_JSON, clear_config_cache, int_to_minified_name
from reflex.testing import AppHarness

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


def MinificationApp():
    """Test app for state and event handler minification.

    This app is used to test that:
    1. Without minify.json, full state/event names are used
    2. With minify.json, minified names are used based on the config
    """
    import reflex as rx
    from reflex.utils import format

    class RootState(rx.State):
        """Root state for testing."""

        count: int = 0

        @rx.event
        def increment(self):
            """Increment the count."""
            self.count += 1

    class SubState(RootState):
        """Sub state for testing."""

        message: str = "hello"

        @rx.event
        def update_message(self):
            """Update the message."""
            parent = self.parent_state
            assert parent is not None
            assert isinstance(parent, RootState)
            self.message = f"count is {parent.count}"

    # Get formatted event handler names for display
    # Use event_handlers dict to get the actual EventHandler objects
    increment_handler_name = format.format_event_handler(
        RootState.event_handlers["increment"]
    )
    update_handler_name = format.format_event_handler(
        SubState.event_handlers["update_message"]
    )

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                value=RootState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            rx.text(f"Root state name: {RootState.get_name()}", id="root_state_name"),
            rx.text(f"Sub state name: {SubState.get_name()}", id="sub_state_name"),
            rx.text(
                f"Increment handler: {increment_handler_name}",
                id="increment_handler_name",
            ),
            rx.text(
                f"Update handler: {update_handler_name}",
                id="update_handler_name",
            ),
            rx.text("Count: ", id="count_label"),
            rx.text(RootState.count, id="count_value"),
            rx.text("Message: ", id="message_label"),
            rx.text(SubState.message, id="message_value"),
            rx.button("Increment", on_click=RootState.increment, id="increment_btn"),
            rx.button(
                "Update Message", on_click=SubState.update_message, id="update_msg_btn"
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture
def minify_disabled_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start app WITHOUT minify.json (full names).

    Args:
        app_harness_env: AppHarness or AppHarnessProd
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        Running AppHarness instance
    """
    # Clear minify config cache to ensure clean state
    clear_config_cache()

    # No minify.json file - full names will be used
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("minify_disabled"),
        app_name="minify_disabled",
        app_source=MinificationApp,
    ) as harness:
        yield harness


@pytest.fixture
def minify_enabled_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start app WITH minify.json (minified names).

    Args:
        app_harness_env: AppHarness or AppHarnessProd
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        Running AppHarness instance
    """
    # Clear minify config cache to ensure clean state
    clear_config_cache()

    app_root = tmp_path_factory.mktemp("minify_enabled")

    # Create the harness object (but don't start yet)
    harness = app_harness_env.create(
        root=app_root,
        app_name="minify_enabled",
        app_source=MinificationApp,
    )

    # Create minify.json with explicit IDs for our states and events
    # The state paths need to match what get_state_full_path() returns
    # Format: module.StateHierarchy (e.g., "minify_enabled.minify_enabled.State.RootState")
    # Note: RootState extends rx.State, so the path includes State in the hierarchy
    # Version 2 format: string IDs and nested events
    app_module = "minify_enabled.minify_enabled"
    root_state_path = f"{app_module}.State.RootState"
    sub_state_path = f"{app_module}.State.RootState.SubState"
    minify_config = {
        "version": 1,
        "states": {
            # Base State needs an ID too since it's in the hierarchy
            "reflex.state.State": "a",
            # RootState extends State, so path is module.State.RootState
            root_state_path: "k",  # int_to_minified_name(10) = 'k'
            # SubState extends RootState, so path is module.State.RootState.SubState
            sub_state_path: "l",  # int_to_minified_name(11) = 'l'
        },
        "events": {
            # Events are now nested under their state path
            root_state_path: {
                "increment": "f",  # int_to_minified_name(5) = 'f'
            },
            sub_state_path: {
                "update_message": "h",  # int_to_minified_name(7) = 'h'
            },
        },
    }

    # Write minify.json to the app root directory
    minify_path = app_root / MINIFY_JSON
    minify_path.write_text(json.dumps(minify_config, indent=2))

    with harness:
        yield harness


@pytest.fixture
def driver_disabled(
    minify_disabled_app: AppHarness,
) -> Generator[WebDriver, None, None]:
    """Get browser instance for disabled mode app.

    Args:
        minify_disabled_app: harness for the app

    Yields:
        WebDriver instance.
    """
    assert minify_disabled_app.app_instance is not None, "app is not running"
    driver = minify_disabled_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture
def driver_enabled(
    minify_enabled_app: AppHarness,
) -> Generator[WebDriver, None, None]:
    """Get browser instance for enabled mode app.

    Args:
        minify_enabled_app: harness for the app

    Yields:
        WebDriver instance.
    """
    assert minify_enabled_app.app_instance is not None, "app is not running"
    driver = minify_enabled_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def test_minification_disabled(
    minify_disabled_app: AppHarness,
    driver_disabled: WebDriver,
) -> None:
    """Test that without minify.json, full state and event names are used.

    Args:
        minify_disabled_app: harness for the app
        driver_disabled: WebDriver instance
    """
    assert minify_disabled_app.app_instance is not None

    # Wait for the app to load
    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver_disabled.find_element(By.ID, "token")
    )
    assert token_input
    token = minify_disabled_app.poll_for_value(token_input)
    assert token

    # Check state names are full names (not minified)
    root_state_name_el = driver_disabled.find_element(By.ID, "root_state_name")
    sub_state_name_el = driver_disabled.find_element(By.ID, "sub_state_name")

    root_state_name = root_state_name_el.text
    sub_state_name = sub_state_name_el.text

    # In disabled mode, names should be the full module___class_name format
    assert "root_state" in root_state_name.lower()
    assert "sub_state" in sub_state_name.lower()
    # Full names should be long (not single char minified names)
    # Extract just the state name part after "Root state name: "
    root_name_only = (
        root_state_name.split(": ")[-1] if ": " in root_state_name else root_state_name
    )
    sub_name_only = (
        sub_state_name.split(": ")[-1] if ": " in sub_state_name else sub_state_name
    )
    assert len(root_name_only) > 5, f"Expected long name, got: {root_name_only}"
    assert len(sub_name_only) > 5, f"Expected long name, got: {sub_name_only}"

    # Check event handler names are full names (not minified)
    increment_handler_el = driver_disabled.find_element(By.ID, "increment_handler_name")
    update_handler_el = driver_disabled.find_element(By.ID, "update_handler_name")

    increment_handler = increment_handler_el.text
    update_handler = update_handler_el.text

    # In disabled mode, event handler names should contain the full method names
    assert "increment" in increment_handler.lower()
    assert "update_message" in update_handler.lower()
    # The format should be "state_name.method_name", so check for the dot
    assert "." in increment_handler
    assert "." in update_handler

    # Test that state updates work
    count_value = driver_disabled.find_element(By.ID, "count_value")
    assert count_value.text == "0"

    increment_btn = driver_disabled.find_element(By.ID, "increment_btn")
    increment_btn.click()

    # Wait for count to update
    AppHarness._poll_for(lambda: count_value.text == "1")
    assert count_value.text == "1"


def test_minification_enabled(
    minify_enabled_app: AppHarness,
    driver_enabled: WebDriver,
) -> None:
    """Test that with minify.json, minified state and event names are used.

    Args:
        minify_enabled_app: harness for the app
        driver_enabled: WebDriver instance
    """
    assert minify_enabled_app.app_instance is not None

    # Wait for the app to load
    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver_enabled.find_element(By.ID, "token")
    )
    assert token_input
    token = minify_enabled_app.poll_for_value(token_input)
    assert token

    # Check state names are minified
    root_state_name_el = driver_enabled.find_element(By.ID, "root_state_name")
    sub_state_name_el = driver_enabled.find_element(By.ID, "sub_state_name")

    root_state_name = root_state_name_el.text
    sub_state_name = sub_state_name_el.text

    # In enabled mode with minify.json, names should be minified
    # RootState has state_id=10 -> 'k'
    # SubState has state_id=11 -> 'l'
    expected_root_minified = int_to_minified_name(10)
    expected_sub_minified = int_to_minified_name(11)

    assert expected_root_minified in root_state_name
    assert expected_sub_minified in sub_state_name

    # Check event handler names are minified
    increment_handler_el = driver_enabled.find_element(By.ID, "increment_handler_name")
    update_handler_el = driver_enabled.find_element(By.ID, "update_handler_name")

    increment_handler_text = increment_handler_el.text
    update_handler_text = update_handler_el.text

    # Extract just the handler name part after "Increment handler: "
    increment_handler = (
        increment_handler_text.split(": ")[-1]
        if ": " in increment_handler_text
        else increment_handler_text
    )
    update_handler = (
        update_handler_text.split(": ")[-1]
        if ": " in update_handler_text
        else update_handler_text
    )

    # In enabled mode with minify.json:
    # - increment has event_id=5 -> 'f'
    # - update_message has event_id=7 -> 'h'
    expected_increment_minified = int_to_minified_name(5)
    expected_update_minified = int_to_minified_name(7)

    # Event handler format: "state_name.event_name"
    # For increment: "k.f" (state_id=10 -> 'k', event_id=5 -> 'f')
    # For update_message: "k.l.h" (state_id=10.11 -> 'k.l', event_id=7 -> 'h')
    assert increment_handler.endswith(f".{expected_increment_minified}"), (
        f"Expected minified event name ending with '.{expected_increment_minified}', "
        f"got: {increment_handler}"
    )
    assert update_handler.endswith(f".{expected_update_minified}"), (
        f"Expected minified event name ending with '.{expected_update_minified}', "
        f"got: {update_handler}"
    )

    # The handler names should NOT contain the original method names
    assert "increment" not in increment_handler.lower(), (
        f"Expected minified name without 'increment', got: {increment_handler}"
    )
    assert "update_message" not in update_handler.lower(), (
        f"Expected minified name without 'update_message', got: {update_handler}"
    )

    # Test that state updates work with minified names
    count_value = driver_enabled.find_element(By.ID, "count_value")
    assert count_value.text == "0"

    increment_btn = driver_enabled.find_element(By.ID, "increment_btn")
    increment_btn.click()

    # Wait for count to update
    AppHarness._poll_for(lambda: count_value.text == "1")
    assert count_value.text == "1"

    # Test substate event handler works with minified names
    message_value = driver_enabled.find_element(By.ID, "message_value")
    assert message_value.text == "hello"

    update_msg_btn = driver_enabled.find_element(By.ID, "update_msg_btn")
    update_msg_btn.click()

    # Wait for message to update
    AppHarness._poll_for(lambda: "count is 1" in message_value.text)
    assert message_value.text == "count is 1"
