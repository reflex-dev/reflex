"""Integration tests for client side storage."""

from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_base.constants.state import FIELD_MARKER

from reflex.testing import AppHarness

from . import utils


def ClientSide():
    """App for testing client-side state."""
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
        # cookies with default settings
        c1: str = rx.Cookie()
        c2: str = rx.Cookie("c2 default")

        # cookies with custom settings
        c3: str = rx.Cookie(max_age=2)  # expires after 2 second
        c4: str = rx.Cookie(same_site="strict")
        c5: str = rx.Cookie(path="/foo/")  # only accessible on `/foo/`
        c6: str = rx.Cookie(name="c6")
        c7: str = rx.Cookie("c7 default")

        # local storage with default settings
        l1: str = rx.LocalStorage()
        l2: str = rx.LocalStorage("l2 default")

        # local storage with custom settings
        l3: str = rx.LocalStorage(name="l3")
        l4: str = rx.LocalStorage("l4 default")

        # Sync'd local storage
        l5: str = rx.LocalStorage(sync=True)
        l6: str = rx.LocalStorage(sync=True, name="l6")

        # Session storage
        s1: str = rx.SessionStorage()
        s2: str = rx.SessionStorage("s2 default")
        s3: str = rx.SessionStorage(name="s3")

        def set_l6(self, my_param: str):
            self.l6 = my_param

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
            rx.box(ClientSideSubState.c1, id="c1"),
            rx.box(ClientSideSubState.c2, id="c2"),
            rx.box(ClientSideSubState.c3, id="c3"),
            rx.box(ClientSideSubState.c4, id="c4"),
            rx.box(ClientSideSubState.c5, id="c5"),
            rx.box(ClientSideSubState.c6, id="c6"),
            rx.box(ClientSideSubState.c7, id="c7"),
            rx.box(ClientSideSubState.l1, id="l1"),
            rx.box(ClientSideSubState.l2, id="l2"),
            rx.box(ClientSideSubState.l3, id="l3"),
            rx.box(ClientSideSubState.l4, id="l4"),
            rx.box(ClientSideSubState.l5, id="l5"),
            rx.box(ClientSideSubState.l6, id="l6"),
            rx.box(ClientSideSubState.s1, id="s1"),
            rx.box(ClientSideSubState.s2, id="s2"),
            rx.box(ClientSideSubState.s3, id="s3"),
            rx.box(ClientSideSubSubState.c1s, id="c1s"),
            rx.box(ClientSideSubSubState.l1s, id="l1s"),
            rx.box(ClientSideSubSubState.s1s, id="s1s"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(index, route="/foo")


@pytest.fixture(scope="module")
def client_side(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start ClientSide app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_side"),
        app_source=ClientSide,
    ) as harness:
        yield harness


@pytest.fixture
def local_storage(page: Page) -> Generator[utils.LocalStorage, None, None]:
    """Get an instance of the local storage helper.

    Args:
        page: Playwright page instance.

    Yields:
        Local storage helper.
    """
    ls = utils.LocalStorage(page)
    yield ls
    ls.clear()


@pytest.fixture
def session_storage(page: Page) -> Generator[utils.SessionStorage, None, None]:
    """Get an instance of the session storage helper.

    Args:
        page: Playwright page instance.

    Yields:
        Session storage helper.
    """
    ss = utils.SessionStorage(page)
    yield ss
    ss.clear()


@pytest.fixture(autouse=True)
def delete_all_cookies(page: Page) -> Generator[None, None, None]:
    """Delete all cookies after each test.

    Args:
        page: Playwright page instance.

    Yields:
        None
    """
    yield
    page.context.clear_cookies()


def cookie_info_map(page: Page) -> dict[str, dict]:
    """Get a map of cookie names to cookie info.

    Args:
        page: Playwright page instance.

    Returns:
        A map of cookie names to cookie info.
    """
    return {
        cookie_info["name"]: dict(cookie_info) for cookie_info in page.context.cookies()
    }


@pytest.mark.asyncio
async def test_client_side_state(
    client_side: AppHarness,
    page: Page,
    local_storage: utils.LocalStorage,
    session_storage: utils.SessionStorage,
):
    """Test client side state.

    Args:
        client_side: harness for ClientSide app.
        page: Playwright page instance.
        local_storage: Local storage helper.
        session_storage: Session storage helper.
    """
    app = client_side.app_instance
    assert app is not None
    assert client_side.frontend_url is not None
    page.goto(client_side.frontend_url)

    def set_sub(var: str, value: str):
        state_var_input = page.locator("#state_var")
        input_value_input = page.locator("#input_value")
        set_sub_state_button = page.locator("#set_sub_state")
        expect(state_var_input).to_have_value("")
        expect(input_value_input).to_have_value("")

        state_var_input.fill(var)
        input_value_input.fill(value)
        set_sub_state_button.click()

    def set_sub_sub(var: str, value: str):
        state_var_input = page.locator("#state_var")
        input_value_input = page.locator("#input_value")
        set_sub_sub_state_button = page.locator("#set_sub_sub_state")
        expect(state_var_input).to_have_value("")
        expect(input_value_input).to_have_value("")

        state_var_input.fill(var)
        input_value_input.fill(value)
        set_sub_sub_state_button.click()

    token = utils.poll_for_token(page)

    c1 = page.locator("#c1")
    c2 = page.locator("#c2")
    c3 = page.locator("#c3")
    c4 = page.locator("#c4")
    c5 = page.locator("#c5")
    c6 = page.locator("#c6")
    c7 = page.locator("#c7")
    l1 = page.locator("#l1")
    l2 = page.locator("#l2")
    l3 = page.locator("#l3")
    l4 = page.locator("#l4")
    s1 = page.locator("#s1")
    s2 = page.locator("#s2")
    s3 = page.locator("#s3")
    c1s = page.locator("#c1s")
    l1s = page.locator("#l1s")
    s1s = page.locator("#s1s")

    # assert on defaults where present
    expect(c1).to_have_text("")
    expect(c2).to_have_text("c2 default")
    expect(c3).to_have_text("")
    expect(c4).to_have_text("")
    expect(c5).to_have_text("")
    expect(c6).to_have_text("")
    expect(c7).to_have_text("c7 default")
    expect(l1).to_have_text("")
    expect(l2).to_have_text("l2 default")
    expect(l3).to_have_text("")
    expect(l4).to_have_text("l4 default")
    expect(s1).to_have_text("")
    expect(s2).to_have_text("s2 default")
    expect(s3).to_have_text("")
    expect(c1s).to_have_text("")
    expect(l1s).to_have_text("")
    expect(s1s).to_have_text("")

    # no cookies should be set yet!
    assert not page.context.cookies()
    local_storage_items = local_storage.items()
    local_storage_items.pop("last_compiled_theme", None)
    local_storage_items.pop("theme", None)
    assert not local_storage_items

    # set some cookies and local storage values
    set_sub("c1", "c1 value")
    set_sub("c2", "c2 value")
    set_sub("c4", "c4 value")
    set_sub("c5", "c5 value")
    set_sub("c6", "c6 throwaway value")
    set_sub("c6", "c6 value")
    set_sub("c7", "c7 value")
    set_sub("l1", "l1 value")
    set_sub("l2", "l2 value")
    set_sub("l3", "l3 value")
    set_sub("l4", "l4 value")
    set_sub("s1", "s1 value")
    set_sub("s2", "s2 value")
    set_sub("s3", "s3 value")
    set_sub_sub("c1s", "c1s value")
    set_sub_sub("l1s", "l1s value")
    set_sub_sub("s1s", "s1s value")

    sub_state_name = client_side.get_full_state_name([
        "_client_side_state",
        "_client_side_sub_state",
    ])
    sub_sub_state_name = client_side.get_full_state_name([
        "_client_side_state",
        "_client_side_sub_state",
        "_client_side_sub_sub_state",
    ])

    def _exp(name: str, value: str, path: str = "/", same_site: str = "Lax") -> dict:
        return {
            "domain": "localhost",
            "httpOnly": False,
            "name": name,
            "path": path,
            "sameSite": same_site,
            "secure": False,
            "value": value,
        }

    exp_cookies = {
        f"{sub_state_name}.c1" + FIELD_MARKER: _exp(
            f"{sub_state_name}.c1" + FIELD_MARKER, "c1%20value"
        ),
        f"{sub_state_name}.c2" + FIELD_MARKER: _exp(
            f"{sub_state_name}.c2" + FIELD_MARKER, "c2%20value"
        ),
        f"{sub_state_name}.c4" + FIELD_MARKER: _exp(
            f"{sub_state_name}.c4" + FIELD_MARKER, "c4%20value", same_site="Strict"
        ),
        "c6": _exp("c6", "c6%20value"),
        f"{sub_state_name}.c7" + FIELD_MARKER: _exp(
            f"{sub_state_name}.c7" + FIELD_MARKER, "c7%20value"
        ),
        f"{sub_sub_state_name}.c1s" + FIELD_MARKER: _exp(
            f"{sub_sub_state_name}.c1s" + FIELD_MARKER, "c1s%20value"
        ),
    }
    AppHarness.expect(
        lambda: all(cookie_key in cookie_info_map(page) for cookie_key in exp_cookies)
    )
    cookies = cookie_info_map(page)
    for exp_cookie_key, exp_cookie_data in exp_cookies.items():
        got = cookies.pop(exp_cookie_key)
        got.pop("expires", None)
        assert got == exp_cookie_data
    # assert all cookies have been popped for this page
    assert not cookies

    # Test cookie with expiry by itself to avoid timing flakiness
    set_sub("c3", "c3 value")
    AppHarness.expect(
        lambda: f"{sub_state_name}.c3" + FIELD_MARKER in cookie_info_map(page)
    )
    c3_cookie = cookie_info_map(page)[f"{sub_state_name}.c3" + FIELD_MARKER]
    assert c3_cookie.pop("expires") not in (None, -1)
    assert c3_cookie == _exp(f"{sub_state_name}.c3" + FIELD_MARKER, "c3%20value")
    await asyncio.sleep(2)  # wait for c3 to expire
    assert f"{sub_state_name}.c3" + FIELD_MARKER not in cookie_info_map(page)

    local_storage_items = local_storage.items()
    local_storage_items.pop("last_compiled_theme", None)
    local_storage_items.pop("theme", None)
    assert local_storage_items.pop(f"{sub_state_name}.l1" + FIELD_MARKER) == "l1 value"
    assert local_storage_items.pop(f"{sub_state_name}.l2" + FIELD_MARKER) == "l2 value"
    assert local_storage_items.pop("l3") == "l3 value"
    assert local_storage_items.pop(f"{sub_state_name}.l4" + FIELD_MARKER) == "l4 value"
    assert (
        local_storage_items.pop(f"{sub_sub_state_name}.l1s" + FIELD_MARKER)
        == "l1s value"
    )
    assert not local_storage_items

    session_storage_items = session_storage.items()
    session_storage_items.pop("token", None)
    assert (
        session_storage_items.pop(f"{sub_state_name}.s1" + FIELD_MARKER) == "s1 value"
    )
    assert (
        session_storage_items.pop(f"{sub_state_name}.s2" + FIELD_MARKER) == "s2 value"
    )
    assert session_storage_items.pop("s3") == "s3 value"
    assert (
        session_storage_items.pop(f"{sub_sub_state_name}.s1s" + FIELD_MARKER)
        == "s1s value"
    )
    assert not session_storage_items

    expect(c1).to_have_text("c1 value")
    expect(c2).to_have_text("c2 value")
    expect(c3).to_have_text("c3 value")
    expect(c4).to_have_text("c4 value")
    expect(c5).to_have_text("c5 value")
    expect(c6).to_have_text("c6 value")
    expect(c7).to_have_text("c7 value")
    expect(l1).to_have_text("l1 value")
    expect(l2).to_have_text("l2 value")
    expect(l3).to_have_text("l3 value")
    expect(l4).to_have_text("l4 value")
    expect(s1).to_have_text("s1 value")
    expect(s2).to_have_text("s2 value")
    expect(s3).to_have_text("s3 value")
    expect(c1s).to_have_text("c1s value")
    expect(l1s).to_have_text("l1s value")
    expect(s1s).to_have_text("s1s value")

    # navigate to the /foo route
    with utils.poll_for_navigation(page):
        page.goto(client_side.frontend_url.removesuffix("/") + "/foo/")

    # locators are re-evaluated on each use
    c1 = page.locator("#c1")
    c2 = page.locator("#c2")
    c3 = page.locator("#c3")
    c4 = page.locator("#c4")
    c5 = page.locator("#c5")
    c6 = page.locator("#c6")
    c7 = page.locator("#c7")
    l1 = page.locator("#l1")
    l2 = page.locator("#l2")
    l3 = page.locator("#l3")
    l4 = page.locator("#l4")
    s1 = page.locator("#s1")
    s2 = page.locator("#s2")
    s3 = page.locator("#s3")
    c1s = page.locator("#c1s")
    l1s = page.locator("#l1s")
    s1s = page.locator("#s1s")

    expect(c1).to_have_text("c1 value")
    expect(c2).to_have_text("c2 value")
    expect(c3).to_have_text("")  # cookie expired so value removed from state
    expect(c4).to_have_text("c4 value")
    expect(c5).to_have_text("c5 value")
    expect(c6).to_have_text("c6 value")
    expect(c7).to_have_text("c7 value")
    expect(l1).to_have_text("l1 value")
    expect(l2).to_have_text("l2 value")
    expect(l3).to_have_text("l3 value")
    expect(l4).to_have_text("l4 value")
    expect(s1).to_have_text("s1 value")
    expect(s2).to_have_text("s2 value")
    expect(s3).to_have_text("s3 value")
    expect(c1s).to_have_text("c1s value")
    expect(l1s).to_have_text("l1s value")
    expect(s1s).to_have_text("s1s value")

    # set a new token to force reloading the values from client
    page.evaluate("() => window.sessionStorage.setItem('token', '')")
    page.reload()

    # wait for the backend connection to send the token (again)
    token = utils.poll_for_token(page)

    expect(page.locator("#c1")).to_have_text("c1 value")
    expect(page.locator("#c2")).to_have_text("c2 value")
    expect(page.locator("#c3")).to_have_text("")
    expect(page.locator("#c4")).to_have_text("c4 value")
    expect(page.locator("#c5")).to_have_text("c5 value")
    expect(page.locator("#c6")).to_have_text("c6 value")
    expect(page.locator("#c7")).to_have_text("c7 value")
    expect(page.locator("#l1")).to_have_text("l1 value")
    expect(page.locator("#l2")).to_have_text("l2 value")
    expect(page.locator("#l3")).to_have_text("l3 value")
    expect(page.locator("#l4")).to_have_text("l4 value")
    expect(page.locator("#s1")).to_have_text("s1 value")
    expect(page.locator("#s2")).to_have_text("s2 value")
    expect(page.locator("#s3")).to_have_text("s3 value")
    expect(page.locator("#c1s")).to_have_text("c1s value")
    expect(page.locator("#l1s")).to_have_text("l1s value")
    expect(page.locator("#s1s")).to_have_text("s1s value")

    # make sure c5 cookie shows up on the `/foo` route
    AppHarness.expect(
        lambda: f"{sub_state_name}.c5" + FIELD_MARKER in cookie_info_map(page)
    )
    c5_cookie = cookie_info_map(page)[f"{sub_state_name}.c5" + FIELD_MARKER]
    c5_cookie.pop("expires", None)
    assert c5_cookie == _exp(
        f"{sub_state_name}.c5" + FIELD_MARKER, "c5%20value", path="/foo/"
    )

    # Open a new tab to check that sync'd local storage is working
    main_tab = page
    new_tab = page.context.new_page()
    new_tab.goto(client_side.frontend_url)

    def new_tab_set_sub(var: str, value: str):
        state_var_input = new_tab.locator("#state_var")
        input_value_input = new_tab.locator("#input_value")
        set_sub_state_button = new_tab.locator("#set_sub_state")
        expect(state_var_input).to_have_value("")
        expect(input_value_input).to_have_value("")
        state_var_input.fill(var)
        input_value_input.fill(value)
        set_sub_state_button.click()

    # New tab should have a different state token.
    assert utils.poll_for_token(new_tab) != token

    # Set values and check them in the new tab.
    new_tab_set_sub("l5", "l5 value")
    new_tab_set_sub("l6", "l6 value")
    expect(new_tab.locator("#l6")).to_have_text("l6 value")
    expect(new_tab.locator("#l5")).to_have_text("l5 value")

    # Set session storage values in the new tab
    new_tab_set_sub("s1", "other tab s1")
    expect(new_tab.locator("#s1")).to_have_text("other tab s1")
    expect(new_tab.locator("#s2")).to_have_text("s2 default")
    expect(new_tab.locator("#s3")).to_have_text("")

    # Switch back to main window — the values should have updated automatically.
    expect(main_tab.locator("#l6")).to_have_text("l6 value")
    expect(main_tab.locator("#l5")).to_have_text("l5 value")
    expect(main_tab.locator("#s1")).to_have_text("s1 value")
    expect(main_tab.locator("#s2")).to_have_text("s2 value")
    expect(main_tab.locator("#s3")).to_have_text("s3 value")

    new_tab.close()

    # Simulate state expiration
    main_tab.locator("#new_token").click()

    # Trigger event to get a new instance of the state since the old was expired.
    set_sub("c1", "c1 post expire")

    expect(main_tab.locator("#c1")).to_have_text("c1 post expire")
    expect(main_tab.locator("#c2")).to_have_text("c2 value")
    expect(main_tab.locator("#c3")).to_have_text("")
    expect(main_tab.locator("#c4")).to_have_text("c4 value")
    expect(main_tab.locator("#c5")).to_have_text("c5 value")
    expect(main_tab.locator("#c6")).to_have_text("c6 value")
    expect(main_tab.locator("#c7")).to_have_text("c7 value")
    expect(main_tab.locator("#l1")).to_have_text("l1 value")
    expect(main_tab.locator("#l2")).to_have_text("l2 value")
    expect(main_tab.locator("#l3")).to_have_text("l3 value")
    expect(main_tab.locator("#l4")).to_have_text("l4 value")
    expect(main_tab.locator("#s1")).to_have_text("s1 value")
    expect(main_tab.locator("#s2")).to_have_text("s2 value")
    expect(main_tab.locator("#s3")).to_have_text("s3 value")
    expect(main_tab.locator("#c1s")).to_have_text("c1s value")
    expect(main_tab.locator("#l1s")).to_have_text("l1s value")
    expect(main_tab.locator("#s1s")).to_have_text("s1s value")

    # clear the cookie jar and local storage, ensure state reset to default
    page.context.clear_cookies()
    local_storage.clear()

    # refresh the page to trigger re-hydrate
    page.reload()

    # wait for the backend connection to send the token (again)
    utils.poll_for_token(page)

    # all values should be back to their defaults
    expect(page.locator("#c1")).to_have_text("")
    expect(page.locator("#c2")).to_have_text("c2 default")
    expect(page.locator("#c3")).to_have_text("")
    expect(page.locator("#c4")).to_have_text("")
    expect(page.locator("#c5")).to_have_text("")
    expect(page.locator("#c6")).to_have_text("")
    expect(page.locator("#c7")).to_have_text("c7 default")
    expect(page.locator("#l1")).to_have_text("")
    expect(page.locator("#l2")).to_have_text("l2 default")
    expect(page.locator("#l3")).to_have_text("")
    expect(page.locator("#l4")).to_have_text("l4 default")
    expect(page.locator("#c1s")).to_have_text("")
    expect(page.locator("#l1s")).to_have_text("")


def test_json_cookie_values(
    client_side: AppHarness,
    page: Page,
):
    """Test that JSON-formatted cookie values are preserved as strings.

    Args:
        client_side: harness for ClientSide app.
        page: Playwright page instance.
    """
    app = client_side.app_instance
    assert app is not None
    assert client_side.frontend_url is not None
    page.goto(client_side.frontend_url)

    def set_sub(var: str, value: str):
        state_var_input = page.locator("#state_var")
        input_value_input = page.locator("#input_value")
        set_sub_state_button = page.locator("#set_sub_state")
        expect(state_var_input).to_have_value("")
        expect(input_value_input).to_have_value("")

        state_var_input.fill(var)
        input_value_input.fill(value)
        set_sub_state_button.click()

    def _assert_json_cookie_with_refresh(cookie_id: str, json_value: str):
        """Helper function to test JSON cookie values with browser refresh.

        Args:
            cookie_id: ID of the cookie element to manipulate.
            json_value: JSON string to set as the cookie value.
        """
        utils.poll_for_token(page)
        element = page.locator(f"#{cookie_id}")
        set_sub(cookie_id, json_value)
        expect(element).to_have_text(json_value)

        page.reload()
        utils.poll_for_token(page)
        element = page.locator(f"#{cookie_id}")
        expect(element).to_have_text(json_value)

    json_dict = '{"access_token": "redacted", "refresh_token": "redacted", "created_at": 1234567890, "expires_in": 3600}'
    _assert_json_cookie_with_refresh("c1", json_dict)

    json_array = '["item1", "item2", "item3"]'
    _assert_json_cookie_with_refresh("c2", json_array)

    complex_json = '{"user": {"id": 123, "name": "test"}, "settings": {"theme": "dark", "notifications": true}, "data": [1, 2, 3]}'
    _assert_json_cookie_with_refresh("c1", complex_json)

    json_with_escapes = (
        '{"message": "Hello \\"world\\"", "path": "/api/v1", "count": 42}'
    )
    _assert_json_cookie_with_refresh("c2", json_with_escapes)

    empty_json_obj = "{}"
    _assert_json_cookie_with_refresh("c1", empty_json_obj)

    empty_json_array = "[]"
    _assert_json_cookie_with_refresh("c2", empty_json_array)
