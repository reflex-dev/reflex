"""Browser integration tests for client-side state storage."""

from __future__ import annotations

import re
from collections.abc import Generator
from typing import Any

import pytest
from playwright.sync_api import BrowserContext, Page, expect
from reflex_base.constants.state import FIELD_MARKER

from reflex.testing import AppHarness


def ClientSide():
    """Build an app that exercises cookie, local, and session storage state."""
    import uuid

    import reflex as rx

    class ClientSideState(rx.State):
        state_var: str = ""
        input_value: str = ""

        @rx.event
        def set_state_var(self, value: str):
            self.state_var = value

        @rx.event
        def set_input_value(self, value: str):
            self.input_value = value

        @rx.event
        def reset_token_no_hydrate(self):
            return rx.run_script(
                f"{{token = '{uuid.uuid4()}'; window.sessionStorage.setItem('token', token);}}"
            )

    class ClientSideSubState(ClientSideState):
        c1: str = rx.Cookie()
        c2: str = rx.Cookie("c2 default")
        c3: str = rx.Cookie(max_age=2)
        c4: str = rx.Cookie(same_site="strict")
        c5: str = rx.Cookie(path="/foo/")
        c6: str = rx.Cookie(name="c6")
        c7: str = rx.Cookie("c7 default")
        l1: str = rx.LocalStorage()
        l2: str = rx.LocalStorage("l2 default")
        l3: str = rx.LocalStorage(name="l3")
        l4: str = rx.LocalStorage("l4 default")
        l5: str = rx.LocalStorage(sync=True)
        l6: str = rx.LocalStorage(sync=True, name="l6")
        s1: str = rx.SessionStorage()
        s2: str = rx.SessionStorage("s2 default")
        s3: str = rx.SessionStorage(name="s3")

        @rx.event
        def set_var(self):
            setattr(self, self.state_var, self.input_value)
            self.state_var = self.input_value = ""

    class ClientSideSubSubState(ClientSideSubState):
        c1s: str = rx.Cookie()
        l1s: str = rx.LocalStorage()
        s1s: str = rx.SessionStorage()

        @rx.event
        def set_var(self):
            setattr(self, self.state_var, self.input_value)
            self.state_var = self.input_value = ""

    def index():
        return rx.fragment(
            rx.input(
                value=ClientSideState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button(
                "New Token - No Hydrate",
                id="new_token",
                on_click=ClientSideState.reset_token_no_hydrate,
            ),
            rx.input(
                placeholder="state var",
                value=ClientSideState.state_var,
                on_change=ClientSideState.setvar("state_var"),
                id="state_var",
            ),
            rx.input(
                placeholder="input value",
                value=ClientSideState.input_value,
                on_change=ClientSideState.setvar("input_value"),
                id="input_value",
            ),
            rx.button(
                "Set ClientSideSubState",
                on_click=ClientSideSubState.set_var,
                id="set_sub_state",
            ),
            rx.button(
                "Set ClientSideSubSubState",
                on_click=ClientSideSubSubState.set_var,
                id="set_sub_sub_state",
            ),
            *(
                rx.box(getattr(ClientSideSubState, name), id=name)
                for name in (
                    "c1",
                    "c2",
                    "c3",
                    "c4",
                    "c5",
                    "c6",
                    "c7",
                    "l1",
                    "l2",
                    "l3",
                    "l4",
                    "l5",
                    "l6",
                    "s1",
                    "s2",
                    "s3",
                )
            ),
            *(
                rx.box(getattr(ClientSideSubSubState, name), id=name)
                for name in (
                    "c1s",
                    "l1s",
                    "s1s",
                )
            ),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(index, route="/foo")


@pytest.fixture(scope="module")
def client_side(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start the client-storage app once for this module.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_side"),
        app_source=ClientSide,
    ) as harness:
        yield harness


@pytest.fixture
def opened_page(client_side: AppHarness, page: Page) -> Page:
    """Open a fresh browser page at the client-storage app.

    Returns:
        The page after navigation.
    """
    assert client_side.frontend_url is not None
    page.goto(client_side.frontend_url)
    return page


def _storage(page: Page, name: str) -> dict[str, str]:
    """Read a browser storage area as a plain dictionary.

    Returns:
        The storage key/value pairs.
    """
    return page.evaluate(
        "(name) => Object.fromEntries(Object.entries(window[name]))", name
    )


def _cookie_map(context: BrowserContext) -> dict[str, Any]:
    """Return browser cookies indexed by name.

    Returns:
        The cookies keyed by cookie name.
    """
    cookies: dict[str, Any] = {}
    for cookie in context.cookies():
        if name := cookie.get("name"):
            cookies[name] = cookie
    return cookies


def _set_state_value(page: Page, state_var: str, value: str, *, sub_sub=False):
    """Set a storage-backed state value through the app controls."""
    state_input = page.locator("#state_var")
    value_input = page.locator("#input_value")
    expect(state_input).to_have_value("")
    expect(value_input).to_have_value("")
    state_input.fill(state_var)
    value_input.fill(value)
    page.locator("#set_sub_sub_state" if sub_sub else "#set_sub_state").click()
    expect(state_input).to_have_value("")
    expect(value_input).to_have_value("")


def _expect_displayed_values(page: Page, values: dict[str, str]) -> None:
    for element_id, value in values.items():
        expect(page.locator(f"#{element_id}")).to_have_text(value)


def _wait_for_token(page: Page) -> str:
    token = page.locator("#token")
    expect(token).to_have_value(re.compile(r".+"), timeout=30_000)
    return token.input_value()


def test_client_side_state(client_side: AppHarness, opened_page: Page):
    """Verify storage defaults, persistence, scope, sync, and state recreation."""
    assert client_side.app_instance is not None
    assert client_side.frontend_url is not None
    page = opened_page
    token = _wait_for_token(page)

    defaults = {
        "c1": "",
        "c2": "c2 default",
        "c3": "",
        "c4": "",
        "c5": "",
        "c6": "",
        "c7": "c7 default",
        "l1": "",
        "l2": "l2 default",
        "l3": "",
        "l4": "l4 default",
        "s1": "",
        "s2": "s2 default",
        "s3": "",
        "c1s": "",
        "l1s": "",
        "s1s": "",
    }
    _expect_displayed_values(page, defaults)
    assert not _cookie_map(page.context)
    local_storage = _storage(page, "localStorage")
    local_storage.pop("last_compiled_theme", None)
    local_storage.pop("theme", None)
    assert local_storage == {}

    for name, value in (
        ("c1", "c1 value"),
        ("c2", "c2 value"),
        ("c4", "c4 value"),
        ("c5", "c5 value"),
        ("c6", "c6 throwaway value"),
        ("c6", "c6 value"),
        ("c7", "c7 value"),
        ("l1", "l1 value"),
        ("l2", "l2 value"),
        ("l3", "l3 value"),
        ("l4", "l4 value"),
        ("s1", "s1 value"),
        ("s2", "s2 value"),
        ("s3", "s3 value"),
    ):
        _set_state_value(page, name, value)
    for name, value in (
        ("c1s", "c1s value"),
        ("l1s", "l1s value"),
        ("s1s", "s1s value"),
    ):
        _set_state_value(page, name, value, sub_sub=True)

    sub_state = client_side.get_full_state_name([
        "_client_side_state",
        "_client_side_sub_state",
    ])
    sub_sub_state = client_side.get_full_state_name([
        "_client_side_state",
        "_client_side_sub_state",
        "_client_side_sub_sub_state",
    ])
    cookies = _cookie_map(page.context)
    expected_cookie_values = {
        f"{sub_state}.c1{FIELD_MARKER}": "c1%20value",
        f"{sub_state}.c2{FIELD_MARKER}": "c2%20value",
        f"{sub_state}.c4{FIELD_MARKER}": "c4%20value",
        f"{sub_state}.c5{FIELD_MARKER}": "c5%20value",
        "c6": "c6%20value",
        f"{sub_state}.c7{FIELD_MARKER}": "c7%20value",
        f"{sub_sub_state}.c1s{FIELD_MARKER}": "c1s%20value",
    }
    assert set(cookies) == set(expected_cookie_values)
    for name, value in expected_cookie_values.items():
        assert cookies[name]["value"] == value
        assert cookies[name]["domain"] == "localhost"
        assert cookies[name]["path"] == (
            "/foo/" if name == f"{sub_state}.c5{FIELD_MARKER}" else "/"
        )
        assert cookies[name]["httpOnly"] is False
        assert cookies[name]["secure"] is False
        assert cookies[name]["sameSite"] == (
            "Strict" if name.endswith(f".c4{FIELD_MARKER}") else "Lax"
        )

    _set_state_value(page, "c3", "c3 value")
    expiring_cookie = _cookie_map(page.context)[f"{sub_state}.c3{FIELD_MARKER}"]
    assert expiring_cookie["expires"] > 0
    page.wait_for_timeout(2_100)
    assert f"{sub_state}.c3{FIELD_MARKER}" not in _cookie_map(page.context)

    local_storage = _storage(page, "localStorage")
    local_storage.pop("last_compiled_theme", None)
    local_storage.pop("theme", None)
    assert local_storage == {
        f"{sub_state}.l1{FIELD_MARKER}": "l1 value",
        f"{sub_state}.l2{FIELD_MARKER}": "l2 value",
        "l3": "l3 value",
        f"{sub_state}.l4{FIELD_MARKER}": "l4 value",
        f"{sub_sub_state}.l1s{FIELD_MARKER}": "l1s value",
    }
    session_storage = _storage(page, "sessionStorage")
    session_storage.pop("token", None)
    assert session_storage == {
        f"{sub_state}.s1{FIELD_MARKER}": "s1 value",
        f"{sub_state}.s2{FIELD_MARKER}": "s2 value",
        "s3": "s3 value",
        f"{sub_sub_state}.s1s{FIELD_MARKER}": "s1s value",
    }

    populated_values = defaults.copy()
    populated_values.update({
        "c1": "c1 value",
        "c2": "c2 value",
        "c3": "c3 value",
        "c4": "c4 value",
        "c5": "c5 value",
        "c6": "c6 value",
        "c7": "c7 value",
        "l1": "l1 value",
        "l2": "l2 value",
        "l3": "l3 value",
        "l4": "l4 value",
        "s1": "s1 value",
        "s2": "s2 value",
        "s3": "s3 value",
        "c1s": "c1s value",
        "l1s": "l1s value",
        "s1s": "s1s value",
    })
    _expect_displayed_values(page, populated_values)

    page.goto(f"{client_side.frontend_url.rstrip('/')}/foo/")
    expect(page).to_have_url(re.compile(r"/foo/?$"))
    _expect_displayed_values(
        page,
        {
            "c1": "c1 value",
            "c2": "c2 value",
            "c3": "",
            "c4": "c4 value",
            "c5": "c5 value",
            "c6": "c6 value",
            "c7": "c7 value",
            "l1": "l1 value",
            "l2": "l2 value",
            "l3": "l3 value",
            "l4": "l4 value",
            "s1": "s1 value",
            "s2": "s2 value",
            "s3": "s3 value",
            "c1s": "c1s value",
            "l1s": "l1s value",
            "s1s": "s1s value",
        },
    )
    expect(page.locator("#c5")).to_have_text("c5 value")

    page.evaluate("sessionStorage.setItem('token', '')")
    page.reload()
    token = _wait_for_token(page)
    _expect_displayed_values(
        page,
        {
            "c1": "c1 value",
            "c2": "c2 value",
            "c3": "",
            "c4": "c4 value",
            "c5": "c5 value",
            "c6": "c6 value",
            "c7": "c7 value",
            "l1": "l1 value",
            "l2": "l2 value",
            "l3": "l3 value",
            "l4": "l4 value",
            "s1": "s1 value",
            "s2": "s2 value",
            "s3": "s3 value",
            "c1s": "c1s value",
            "l1s": "l1s value",
            "s1s": "s1s value",
        },
    )
    assert _cookie_map(page.context)[f"{sub_state}.c5{FIELD_MARKER}"]["path"] == "/foo/"

    other_tab = page.context.new_page()
    other_tab.goto(client_side.frontend_url)
    assert _wait_for_token(other_tab) != token
    _set_state_value(other_tab, "l5", "l5 value")
    _set_state_value(other_tab, "l6", "l6 value")
    expect(other_tab.locator("#l5")).to_have_text("l5 value")
    expect(other_tab.locator("#l6")).to_have_text("l6 value")
    _set_state_value(other_tab, "s1", "other tab s1")
    _expect_displayed_values(
        other_tab, {"s1": "other tab s1", "s2": "s2 default", "s3": ""}
    )
    expect(page.locator("#l5")).to_have_text("l5 value")
    expect(page.locator("#l6")).to_have_text("l6 value")
    expect(page.locator("#s1")).to_have_text("s1 value")

    page.locator("#new_token").click()
    _set_state_value(page, "c1", "c1 post expire")
    _expect_displayed_values(
        page,
        {
            "c1": "c1 post expire",
            "c2": "c2 value",
            "c3": "",
            "c4": "c4 value",
            "c5": "c5 value",
            "c6": "c6 value",
            "c7": "c7 value",
            "l1": "l1 value",
            "l2": "l2 value",
            "l3": "l3 value",
            "l4": "l4 value",
            "l5": "l5 value",
            "l6": "l6 value",
            "s1": "s1 value",
            "s2": "s2 value",
            "s3": "s3 value",
            "c1s": "c1s value",
            "l1s": "l1s value",
            "s1s": "s1s value",
        },
    )

    page.context.clear_cookies()
    page.evaluate("localStorage.clear()")
    page.reload()
    _wait_for_token(page)
    _expect_displayed_values(
        page,
        defaults
        | {
            "c1s": "",
            "l1s": "",
            "s1": "s1 value",
            "s2": "s2 value",
            "s3": "s3 value",
            "s1s": "s1s value",
        },
    )


def test_json_cookie_values(client_side: AppHarness, opened_page: Page):
    """JSON cookie strings survive refresh without parsing or mutation."""
    assert client_side.frontend_url is not None
    page = opened_page
    _wait_for_token(page)

    def assert_cookie_after_refresh(cookie_id: str, value: str) -> None:
        _set_state_value(page, cookie_id, value)
        expect(page.locator(f"#{cookie_id}")).to_have_text(value)
        page.reload()
        _wait_for_token(page)
        expect(page.locator(f"#{cookie_id}")).to_have_text(value)

    assert_cookie_after_refresh(
        "c1",
        '{"access_token": "redacted", "refresh_token": "redacted", "created_at": 1234567890, "expires_in": 3600}',
    )
    assert_cookie_after_refresh("c2", '["item1", "item2", "item3"]')
    assert_cookie_after_refresh(
        "c1",
        '{"user": {"id": 123, "name": "test"}, "settings": {"theme": "dark", "notifications": true}, "data": [1, 2, 3]}',
    )
    assert_cookie_after_refresh(
        "c2", '{"message": "Hello \\"world\\"", "path": "/api/v1", "count": 42}'
    )
    assert_cookie_after_refresh("c1", "{}")
    assert_cookie_after_refresh("c2", "[]")
