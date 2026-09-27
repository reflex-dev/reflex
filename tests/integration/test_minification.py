"""Integration tests for state and event handler minification."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from selenium.webdriver.common.by import By

from reflex.environment import environment
from reflex.minify import (
    MINIFY_JSON,
    SCHEMA_VERSION,
    clear_config_cache,
    int_to_minified_name,
)
from reflex.testing import AppHarness

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


def MinificationApp():
    """Test app with one root + one substate, each with one event handler."""
    import reflex as rx
    from reflex.utils import format

    class RootState(rx.State):
        count: int = 0
        token_cookie: str = rx.Cookie("")

        @rx.var
        def doubled(self) -> int:
            return self.count * 2

        @rx.event
        def increment(self):
            self.count += 1

        @rx.event
        def save_cookie(self):
            self.token_cookie = f"tok-{self.count}"

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
            rx.text(f"Count key: {RootState.count!s}", id="count_key"),
            rx.text(RootState.count, id="count_value"),
            rx.text(RootState.doubled, id="doubled_value"),
            rx.text(RootState.token_cookie, id="cookie_value"),
            rx.text(SubState.message, id="message_value"),
            rx.button("Increment", on_click=RootState.increment, id="increment_btn"),
            rx.button("Save Cookie", on_click=RootState.save_cookie, id="cookie_btn"),
            rx.button(
                "Update Message", on_click=SubState.update_message, id="update_msg_btn"
            ),
        )

    app = rx.App()
    app.add_page(index)


# The framework states already exist when AppHarness loads this config, well
# after pytest imported ``reflex.state``: installing it renames their Vars too.
_FRAMEWORK_STATES = {
    "reflex.state.State": {"id": "a", "parent": None},
    **{
        f"reflex.state.State.{name}": {
            "id": minified_id,
            "parent": "reflex.state.State",
        }
        for name, minified_id in (
            ("FrontendEventExceptionState", "b"),
            ("OnLoadInternalState", "c"),
            ("UpdateVarsInternalState", "d"),
        )
    },
    "reflex.istate.shared.State.SharedStateBaseInternal": {
        "id": "e",
        "parent": "reflex.state.State",
    },
}
_MINIFY_CONFIG = {
    "version": SCHEMA_VERSION,
    "states": {
        **_FRAMEWORK_STATES,
        "minify_enabled.minify_enabled.State.RootState": {
            "id": "k",  # 10
            "parent": "reflex.state.State",
        },
        "minify_enabled.minify_enabled.State.RootState.SubState": {
            "id": "l",  # 11
            "parent": "minify_enabled.minify_enabled.State.RootState",
        },
    },
    "events": {
        "reflex.state.State": {"hydrate": "a", "set_is_hydrated": "b"},
        "reflex.state.State.OnLoadInternalState": {"on_load_internal": "a"},
        "reflex.state.State.UpdateVarsInternalState": {"update_vars_internal": "a"},
        "reflex.state.State.FrontendEventExceptionState": {
            "handle_frontend_exception": "a"
        },
        "minify_enabled.minify_enabled.State.RootState": {
            "increment": "f",  # 5
            "save_cookie": "g",  # 6
        },
        "minify_enabled.minify_enabled.State.RootState.SubState": {
            "update_message": "h"  # 7
        },
    },
    "vars": {
        "reflex.state.State": {"is_hydrated": "h", "rx_router_session": "s"},
        "minify_enabled.minify_enabled.State.RootState": {
            "count": "c",
            "doubled": "d",
            "token_cookie": "t",
        },
        "minify_enabled.minify_enabled.State.RootState.SubState": {"message": "m"},
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
        monkeypatch.setenv(environment.REFLEX_MINIFY_STATES.name, "1")
        monkeypatch.setenv(environment.REFLEX_MINIFY_EVENTS.name, "1")
        monkeypatch.setenv(environment.REFLEX_MINIFY_VARS.name, "1")
    clear_config_cache()

    app_name = "minify_enabled" if enabled else "minify_disabled"
    app_root = tmp_path_factory.mktemp(app_name)
    harness = app_harness_env.create(
        root=app_root, app_name=app_name, app_source=MinificationApp
    )
    if enabled:
        (app_root / MINIFY_JSON).write_text(json.dumps(_MINIFY_CONFIG))

    try:
        with harness:
            yield enabled, harness
    finally:
        # Put the default names back for the tests that share this process.
        monkeypatch.undo()
        clear_config_cache()


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

    count_key = _text_after_colon(driver.find_element(By.ID, "count_key").text)

    if enabled:
        assert root_name.endswith(int_to_minified_name(10))
        assert sub_name.endswith(int_to_minified_name(11))
        assert (
            increment_name == f"a.{int_to_minified_name(10)}.{int_to_minified_name(5)}"
        )
        assert update_name.endswith(f".{int_to_minified_name(7)}")
        assert "increment" not in increment_name.lower()
        assert "update_message" not in update_name.lower()
        assert count_key == "a__k.c"
    else:
        assert count_key.endswith(".count_rx_state_")
        assert "root_state" in root_name.lower()
        assert "sub_state" in sub_name.lower()
        assert "increment" in increment_name.lower()
        assert "update_message" in update_name.lower()
        assert "." in increment_name
        assert "." in update_name

    # Event dispatch sanity check (must work regardless of minification).
    count = driver.find_element(By.ID, "count_value")
    doubled = driver.find_element(By.ID, "doubled_value")
    assert count.text == "0"
    driver.find_element(By.ID, "increment_btn").click()
    AppHarness.poll_for_or_raise_timeout(lambda: count.text == "1")
    AppHarness.poll_for_or_raise_timeout(lambda: doubled.text == "2")

    # The cookie is stored under the name it has without minification, so
    # turning minification on or off keeps what browsers already hold.
    cookie = driver.find_element(By.ID, "cookie_value")
    driver.find_element(By.ID, "cookie_btn").click()
    AppHarness.poll_for_or_raise_timeout(lambda: cookie.text == "tok-1")
    app_name = "minify_enabled" if enabled else "minify_disabled"
    stored = driver.get_cookie(
        f"reflex___state____state.{app_name}___{app_name}____root_state"
        ".token_cookie_rx_state_"
    )
    assert stored is not None
    assert stored["value"] == "tok-1"

    if enabled:
        # Substate handler dispatch through minified names.
        message = driver.find_element(By.ID, "message_value")
        driver.find_element(By.ID, "update_msg_btn").click()
        AppHarness.poll_for_or_raise_timeout(lambda: "count is 1" in message.text)
        assert message.text == "count is 1"
