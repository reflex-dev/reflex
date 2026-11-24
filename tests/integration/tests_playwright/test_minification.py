"""Integration tests for state and event handler minification."""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.environment import environment
from reflex.minify import MINIFY_JSON, SCHEMA_VERSION, clear_config_cache
from reflex.testing import AppHarness


def MinificationApp():
    """Test app with one root + one substate, each with one event handler."""
    import reflex as rx
    from reflex.utils import format

    class RootState(rx.State):
        count: int = 0
        label: str = "count"

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
            # Reads two fields of one state, which subscribe through one hook.
            rx.text(f"{RootState.label}: {RootState.count}", id="label_and_count"),
            rx.text(SubState.message, id="message_value"),
            rx.button("Increment", on_click=RootState.increment, id="increment_btn"),
            rx.button(
                "Update Message", on_click=SubState.update_message, id="update_msg_btn"
            ),
        )

    app = rx.App()
    app.add_page(index)


# Framework state classes (e.g. ``reflex.state.State``) bake their names when
# ``reflex.state`` is first imported, which under AppHarness is pytest start-up,
# before this config exists — so they are left out here and covered by the
# subprocess tests in ``tests/units/test_minify.py``.
_MINIFY_CONFIG = {
    "version": SCHEMA_VERSION,
    "states": {
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
        monkeypatch.setenv(environment.REFLEX_MINIFY_STATES.name, "1")
        monkeypatch.setenv(environment.REFLEX_MINIFY_EVENTS.name, "1")
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


def test_minification(minify_app: tuple[bool, AppHarness], page: Page) -> None:
    """State and event handler names follow the minify config when enabled."""
    enabled, harness = minify_app
    assert harness.frontend_url is not None
    page.goto(harness.frontend_url)
    expect(page.locator("#token")).not_to_have_value("", timeout=15_000)

    if enabled:
        root, sub, increment, update_message = "k", "l", "f", "h"
    else:
        root = "minify_disabled___minify_disabled____root_state"
        sub = "minify_disabled___minify_disabled____sub_state"
        increment, update_message = "increment", "update_message"
    expect(page.locator("#root_state_name")).to_have_text(f"Root state name: {root}")
    expect(page.locator("#sub_state_name")).to_have_text(f"Sub state name: {sub}")
    expect(page.locator("#increment_handler_name")).to_have_text(
        f"Increment handler: reflex___state____state.{root}.{increment}"
    )
    expect(page.locator("#update_handler_name")).to_have_text(
        f"Update handler: reflex___state____state.{root}.{sub}.{update_message}"
    )

    count = page.locator("#count_value")
    label_and_count = page.locator("#label_and_count")
    expect(count).to_have_text("0")
    expect(label_and_count).to_have_text("count: 0")
    page.locator("#increment_btn").click()
    expect(count).to_have_text("1")
    expect(label_and_count).to_have_text("count: 1")

    page.locator("#update_msg_btn").click()
    expect(page.locator("#message_value")).to_have_text("count is 1")
