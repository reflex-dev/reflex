"""Integration tests for explicit state ID minification."""

from __future__ import annotations

import os
from collections.abc import Generator
from functools import partial
from typing import TYPE_CHECKING

import pytest
from selenium.webdriver.common.by import By

from reflex.environment import StateMinifyMode, environment
from reflex.state import _int_to_minified_name, _state_id_registry
from reflex.testing import AppHarness

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


def StateMinificationApp(root_state_id: int, sub_state_id: int):
    """Test app for state minification.

    Args:
        root_state_id: The state_id for the root state.
        sub_state_id: The state_id for the sub state.
    """
    import reflex as rx

    class RootState(rx.State, state_id=root_state_id):
        """Root state with explicit state_id."""

        count: int = 0

        @rx.event
        def increment(self):
            """Increment the count."""
            self.count += 1

    class SubState(RootState, state_id=sub_state_id):
        """Sub state with explicit state_id."""

        message: str = "hello"

        @rx.event
        def update_message(self):
            """Update the message."""
            parent = self.parent_state
            assert parent is not None
            assert isinstance(parent, RootState)
            self.message = f"count is {parent.count}"

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                value=RootState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            rx.text(f"Root state name: {RootState.get_name()}", id="root_state_name"),
            rx.text(f"Sub state name: {SubState.get_name()}", id="sub_state_name"),
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


@pytest.fixture(autouse=True)
def reset_state_registry():
    """Reset the state_id registry before and after each test."""
    _state_id_registry.clear()
    yield
    _state_id_registry.clear()


@pytest.fixture
def minify_disabled_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start app with REFLEX_MINIFY_STATES=disabled.

    Args:
        app_harness_env: AppHarness or AppHarnessProd
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        Running AppHarness instance
    """
    os.environ["REFLEX_MINIFY_STATES"] = "disabled"
    environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.DISABLED)

    with app_harness_env.create(
        root=tmp_path_factory.mktemp("state_minify_disabled"),
        app_name="state_minify_disabled",
        app_source=partial(StateMinificationApp, root_state_id=0, sub_state_id=1),
    ) as harness:
        yield harness

    # Cleanup
    os.environ.pop("REFLEX_MINIFY_STATES", None)
    environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.DISABLED)


@pytest.fixture
def minify_enabled_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start app with REFLEX_MINIFY_STATES=enabled.

    Args:
        app_harness_env: AppHarness or AppHarnessProd
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        Running AppHarness instance
    """
    os.environ["REFLEX_MINIFY_STATES"] = "enabled"
    environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.ENABLED)

    with app_harness_env.create(
        root=tmp_path_factory.mktemp("state_minify_enabled"),
        app_name="state_minify_enabled",
        app_source=partial(StateMinificationApp, root_state_id=10, sub_state_id=11),
    ) as harness:
        yield harness

    # Cleanup
    os.environ.pop("REFLEX_MINIFY_STATES", None)
    environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.DISABLED)


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


def test_state_minification_disabled(
    minify_disabled_app: AppHarness,
    driver_disabled: WebDriver,
) -> None:
    """Test that DISABLED mode uses full state names.

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

    # Test that state updates work
    count_value = driver_disabled.find_element(By.ID, "count_value")
    assert count_value.text == "0"

    increment_btn = driver_disabled.find_element(By.ID, "increment_btn")
    increment_btn.click()

    # Wait for count to update
    AppHarness._poll_for(lambda: count_value.text == "1")
    assert count_value.text == "1"


def test_state_minification_enabled(
    minify_enabled_app: AppHarness,
    driver_enabled: WebDriver,
) -> None:
    """Test that ENABLED mode uses minified state names.

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

    # In enabled mode with state_id, names should be minified
    # state_id=10 -> 'k', state_id=11 -> 'l'
    expected_root_minified = _int_to_minified_name(10)
    expected_sub_minified = _int_to_minified_name(11)

    assert expected_root_minified in root_state_name
    assert expected_sub_minified in sub_state_name

    # Test that state updates work with minified names
    count_value = driver_enabled.find_element(By.ID, "count_value")
    assert count_value.text == "0"

    increment_btn = driver_enabled.find_element(By.ID, "increment_btn")
    increment_btn.click()

    # Wait for count to update
    AppHarness._poll_for(lambda: count_value.text == "1")
    assert count_value.text == "1"

    # Test substate event handler works
    message_value = driver_enabled.find_element(By.ID, "message_value")
    assert message_value.text == "hello"

    update_msg_btn = driver_enabled.find_element(By.ID, "update_msg_btn")
    update_msg_btn.click()

    # Wait for message to update
    AppHarness._poll_for(lambda: "count is 1" in message_value.text)
    assert message_value.text == "count is 1"
