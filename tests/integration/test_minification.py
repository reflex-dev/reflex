"""Integration tests for state and event handler minification."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from selenium.webdriver.common.by import By

from reflex.environment import MinifyMode, environment
from reflex.minify import MINIFY_JSON, clear_config_cache, int_to_minified_name
from reflex.testing import AppHarness

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


def MinificationApp():
    """Test app with one root + one substate, each with one event handler."""
    import reflex as rx
    from reflex.utils import format

    class RootState(rx.State):
        count: int = 0

        @rx.event
        def increment(self):
            self.count += 1

    class SubState(RootState):
        message: str = "hello"

        @rx.event
        def update_message(self):
            parent = self.parent_state
            assert parent is not None
            assert isinstance(parent, RootState)
            self.message = f"count is {parent.count}"

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
            rx.text(f"Update handler: {update_handler_name}", id="update_handler_name"),
            rx.text(RootState.count, id="count_value"),
            rx.text(SubState.message, id="message_value"),
            rx.button("Increment", on_click=RootState.increment, id="increment_btn"),
            rx.button(
                "Update Message", on_click=SubState.update_message, id="update_msg_btn"
            ),
        )

    app = rx.App()
    app.add_page(index)


# Framework state classes (e.g. ``reflex.state.State``) are deliberately
# absent — the resolver never minifies them.
_MINIFY_CONFIG = {
    "version": 1,
    "states": {
        "minify_enabled.minify_enabled.State.RootState": "k",  # 10
        "minify_enabled.minify_enabled.State.RootState.SubState": "l",  # 11
    },
    "events": {
        "minify_enabled.minify_enabled.State.RootState": {"increment": "f"},  # 5
        "minify_enabled.minify_enabled.State.RootState.SubState": {
            "update_message": "h"  # 7
        },
    },
}


@pytest.fixture(params=[False, True], ids=["disabled", "enabled"])
def minify_app(
    request: pytest.FixtureRequest,
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[bool, AppHarness], None, None]:
    """Run :func:`MinificationApp` with minification on (parametrized).

    Yields:
        ``(minify_enabled, harness)``.
    """
    enabled: bool = request.param
    if enabled:
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )
    clear_config_cache()

    app_name = "minify_enabled" if enabled else "minify_disabled"
    app_root = tmp_path_factory.mktemp(app_name)
    harness = app_harness_env.create(
        root=app_root, app_name=app_name, app_source=MinificationApp
    )
    if enabled:
        (app_root / MINIFY_JSON).write_text(json.dumps(_MINIFY_CONFIG))

    with harness:
        yield enabled, harness


@pytest.fixture
def driver(
    minify_app: tuple[bool, AppHarness],
) -> Generator[WebDriver, None, None]:
    """WebDriver scoped to the parametrized :func:`minify_app`.

    Yields:
        A WebDriver pointed at the running app.
    """
    _enabled, harness = minify_app
    assert harness.app_instance is not None, "app is not running"
    drv = harness.frontend()
    try:
        yield drv
    finally:
        drv.quit()


def _text_after_colon(text: str) -> str:
    """Strip the ``"label: "`` prefix from a UI element's text.

    Args:
        text: The element text.

    Returns:
        The substring after the first ``": "``, or ``text`` unchanged.
    """
    return text.split(": ", 1)[-1] if ": " in text else text


def test_minification(
    minify_app: tuple[bool, AppHarness],
    driver: WebDriver,
) -> None:
    """State and event handler names follow the minify config when enabled."""
    enabled, harness = minify_app
    assert harness.app_instance is not None

    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )
    assert harness.poll_for_value(token_input)

    root_name = driver.find_element(By.ID, "root_state_name").text
    sub_name = driver.find_element(By.ID, "sub_state_name").text
    increment_name = _text_after_colon(
        driver.find_element(By.ID, "increment_handler_name").text
    )
    update_name = _text_after_colon(
        driver.find_element(By.ID, "update_handler_name").text
    )

    if enabled:
        assert int_to_minified_name(10) in root_name
        assert int_to_minified_name(11) in sub_name
        assert increment_name.endswith(f".{int_to_minified_name(5)}")
        assert update_name.endswith(f".{int_to_minified_name(7)}")
        assert "increment" not in increment_name.lower()
        assert "update_message" not in update_name.lower()
    else:
        assert "root_state" in root_name.lower()
        assert "sub_state" in sub_name.lower()
        assert "increment" in increment_name.lower()
        assert "update_message" in update_name.lower()
        assert "." in increment_name
        assert "." in update_name

    # Event dispatch sanity check (must work regardless of minification).
    count = driver.find_element(By.ID, "count_value")
    assert count.text == "0"
    driver.find_element(By.ID, "increment_btn").click()
    AppHarness._poll_for(lambda: count.text == "1")

    if enabled:
        # Substate handler dispatch through minified names.
        message = driver.find_element(By.ID, "message_value")
        driver.find_element(By.ID, "update_msg_btn").click()
        AppHarness._poll_for(lambda: "count is 1" in message.text)
        assert message.text == "count is 1"
