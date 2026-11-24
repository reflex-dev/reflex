"""Integration tests for state and event handler minification."""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_base.registry import RegistrationContext

from reflex.environment import environment
from reflex.minify import MINIFY_JSON, SCHEMA_VERSION, clear_config_cache
from reflex.state import State
from reflex.testing import AppHarness


def MinificationApp():
    """Test app with one root + one substate, each with one event handler."""
    import reflex as rx
    from reflex.utils import format

    class RootState(rx.State):
        count: int = 0
        token_cookie: str = rx.Cookie("")
        label: str = "count"

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
            # Reads two fields of one state, which subscribe through one hook.
            rx.text(f"{RootState.label}: {RootState.count}", id="label_and_count"),
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


@pytest.fixture(params=["disabled", "enabled", "foreign"])
def minify_app(
    request: pytest.FixtureRequest,
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[bool, AppHarness], None, None]:
    """Run :func:`MinificationApp` in each way a ``minify.json`` can reach it.

    ``foreign`` runs it from a process that already loaded another app's
    ``minify.json``, as an embedded test app next to a minified repository.

    Yields:
        ``(minified, harness)``.
    """
    mode: str = request.param
    minified = mode == "enabled"
    if mode != "disabled":
        monkeypatch.setenv(environment.REFLEX_MINIFY_STATES.name, "1")
        monkeypatch.setenv(environment.REFLEX_MINIFY_EVENTS.name, "1")
        monkeypatch.setenv(environment.REFLEX_MINIFY_VARS.name, "1")
    if mode == "foreign":
        outside = tmp_path_factory.mktemp("foreign_config")
        (outside / MINIFY_JSON).write_text(json.dumps(_MINIFY_CONFIG))
        monkeypatch.chdir(outside)
    clear_config_cache()

    # The foreign config names this very app, so only the directory stops it.
    app_name = "minify_disabled" if mode == "disabled" else "minify_enabled"
    app_root = tmp_path_factory.mktemp(app_name)
    harness = app_harness_env.create(
        root=app_root, app_name=app_name, app_source=MinificationApp
    )
    if mode == "enabled":
        (app_root / MINIFY_JSON).write_text(json.dumps(_MINIFY_CONFIG))

    try:
        with harness:
            yield minified, harness
        if mode == "foreign":
            # The embedded app's names do not outlive it.
            resolver = RegistrationContext.get().name_resolver
            assert State.get_name() == (
                resolver.resolve_state_name(State)
                or RegistrationContext.default_state_name(State)
            )
    finally:
        # Put the default names back for the tests that share this process.
        monkeypatch.undo()
        clear_config_cache()


def test_minification(minify_app: tuple[bool, AppHarness], page: Page) -> None:
    """State, event handler and var names follow the minify config when enabled."""
    minified, harness = minify_app
    assert harness.frontend_url is not None
    page.goto(harness.frontend_url)
    expect(page.locator("#token")).not_to_have_value("", timeout=15_000)

    app_name = harness.app_name
    default_root = f"{app_name}___{app_name}____root_state"
    if minified:
        framework, root, sub = "a", "k", "l"
        increment, update_message = "f", "h"
        count_key = "$rx_a__k.c"
    else:
        framework = "reflex___state____state"
        root, sub = default_root, f"{app_name}___{app_name}____sub_state"
        increment, update_message = "increment", "update_message"
        count_key = f"{framework}__{root}.count_rx_state_"
    expect(page.locator("#root_state_name")).to_have_text(f"Root state name: {root}")
    expect(page.locator("#sub_state_name")).to_have_text(f"Sub state name: {sub}")
    expect(page.locator("#increment_handler_name")).to_have_text(
        f"Increment handler: {framework}.{root}.{increment}"
    )
    expect(page.locator("#update_handler_name")).to_have_text(
        f"Update handler: {framework}.{root}.{sub}.{update_message}"
    )
    expect(page.locator("#count_key")).to_have_text(f"Count key: {count_key}")

    count = page.locator("#count_value")
    label_and_count = page.locator("#label_and_count")
    expect(count).to_have_text("0")
    expect(label_and_count).to_have_text("count: 0")
    page.locator("#increment_btn").click()
    expect(count).to_have_text("1")
    expect(page.locator("#doubled_value")).to_have_text("2")
    expect(label_and_count).to_have_text("count: 1")

    # The cookie is stored under the name it has without minification, so
    # turning minification on or off keeps what browsers already hold.
    page.locator("#cookie_btn").click()
    expect(page.locator("#cookie_value")).to_have_text("tok-1")
    cookies = {c.get("name"): c.get("value") for c in page.context.cookies()}
    assert (
        cookies[f"reflex___state____state.{default_root}.token_cookie_rx_state_"]
        == "tok-1"
    )

    page.locator("#update_msg_btn").click()
    expect(page.locator("#message_value")).to_have_text("count is 1")
