"""Integration tests for client side storage."""

from __future__ import annotations

import time
from typing import Generator

import pytest
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from reflex.testing import AppHarness

from . import utils


def ClientSide():
    """App for testing client-side state."""
    import reflex as rx

    class ClientSideState(rx.State):
        state_var: str = ""
        input_value: str = ""

    class ClientSideSubState(ClientSideState):
        # cookies with default settings
        c1: str = rx.Cookie()
        c2: rx.Cookie = "c2 default"  # type: ignore

        # cookies with custom settings
        c3: str = rx.Cookie(max_age=2)  # expires after 2 second
        c4: rx.Cookie = rx.Cookie(same_site="strict")
        c5: str = rx.Cookie(path="/foo/")  # only accessible on `/foo/`
        c6: str = rx.Cookie(name="c6")
        c7: str = rx.Cookie("c7 default")

        # local storage with default settings
        l1: str = rx.LocalStorage()
        l2: rx.LocalStorage = "l2 default"  # type: ignore

        # local storage with custom settings
        l3: str = rx.LocalStorage(name="l3")
        l4: str = rx.LocalStorage("l4 default")

        # Sync'd local storage
        l5: str = rx.LocalStorage(sync=True)
        l6: str = rx.LocalStorage(sync=True, name="l6")

        # Session storage
        s1: str = rx.SessionStorage()
        s2: rx.SessionStorage = "s2 default"  # type: ignore
        s3: str = rx.SessionStorage(name="s3")

        def set_l6(self, my_param: str):
            self.l6 = my_param

        def set_var(self):
            setattr(self, self.state_var, self.input_value)
            self.state_var = self.input_value = ""

    class ClientSideSubSubState(ClientSideSubState):
        c1s: str = rx.Cookie()
        l1s: str = rx.LocalStorage()
        s1s: str = rx.SessionStorage()

        def set_var(self):
            setattr(self, self.state_var, self.input_value)
            self.state_var = self.input_value = ""

    def index():
        return rx.fragment(
            rx.input(
                value=ClientSideState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            rx.input(
                placeholder="state var",
                value=ClientSideState.state_var,
                on_change=ClientSideState.set_state_var,  # type: ignore
                id="state_var",
            ),
            rx.input(
                placeholder="input value",
                value=ClientSideState.input_value,
                on_change=ClientSideState.set_input_value,  # type: ignore
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

    app = rx.App(state=rx.State)
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
        app_source=ClientSide,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(client_side: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the client_side app.

    Args:
        client_side: harness for ClientSide app

    Yields:
        WebDriver instance.
    """
    assert client_side.app_instance is not None, "app is not running"
    driver = client_side.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture()
def local_storage(driver: WebDriver) -> Generator[utils.LocalStorage, None, None]:
    """Get an instance of the local storage helper.

    Args:
        driver: WebDriver instance.

    Yields:
        Local storage helper.
    """
    ls = utils.LocalStorage(driver)
    yield ls
    ls.clear()


@pytest.fixture()
def session_storage(driver: WebDriver) -> Generator[utils.SessionStorage, None, None]:
    """Get an instance of the session storage helper.

    Args:
        driver: WebDriver instance.

    Yields:
        Session storage helper.
    """
    ss = utils.SessionStorage(driver)
    yield ss
    ss.clear()


@pytest.fixture(autouse=True)
def delete_all_cookies(driver: WebDriver) -> Generator[None, None, None]:
    """Delete all cookies after each test.

    Args:
        driver: WebDriver instance.

    Yields:
        None
    """
    yield
    driver.delete_all_cookies()


def cookie_info_map(driver: WebDriver) -> dict[str, dict[str, str]]:
    """Get a map of cookie names to cookie info.

    Args:
        driver: WebDriver instance.

    Returns:
        A map of cookie names to cookie info.
    """
    return {cookie_info["name"]: cookie_info for cookie_info in driver.get_cookies()}


@pytest.mark.asyncio
async def test_client_side_state(
    client_side: AppHarness,
    driver: WebDriver,
    local_storage: utils.LocalStorage,
    session_storage: utils.SessionStorage,
):
    """Test client side state.

    Args:
        client_side: harness for ClientSide app.
        driver: WebDriver instance.
        local_storage: Local storage helper.
        session_storage: Session storage helper.
    """
    app = client_side.app_instance
    assert app is not None
    assert client_side.frontend_url is not None

    def poll_for_token():
        token_input = driver.find_element(By.ID, "token")
        assert token_input

        # wait for the backend connection to send the token
        token = client_side.poll_for_value(token_input)
        assert token is not None
        return token

    def set_sub(var: str, value: str):
        # Get a reference to the cookie manipulation form.
        state_var_input = driver.find_element(By.ID, "state_var")
        input_value_input = driver.find_element(By.ID, "input_value")
        set_sub_state_button = driver.find_element(By.ID, "set_sub_state")
        AppHarness._poll_for(lambda: state_var_input.get_attribute("value") == "")
        AppHarness._poll_for(lambda: input_value_input.get_attribute("value") == "")

        # Set the values.
        state_var_input.send_keys(var)
        input_value_input.send_keys(value)
        set_sub_state_button.click()

    def set_sub_sub(var: str, value: str):
        # Get a reference to the cookie manipulation form.
        state_var_input = driver.find_element(By.ID, "state_var")
        input_value_input = driver.find_element(By.ID, "input_value")
        set_sub_sub_state_button = driver.find_element(By.ID, "set_sub_sub_state")
        AppHarness._poll_for(lambda: state_var_input.get_attribute("value") == "")
        AppHarness._poll_for(lambda: input_value_input.get_attribute("value") == "")

        # Set the values.
        state_var_input.send_keys(var)
        input_value_input.send_keys(value)
        set_sub_sub_state_button.click()

    token = poll_for_token()

    # get a reference to all cookie and local storage elements
    c1 = driver.find_element(By.ID, "c1")
    c2 = driver.find_element(By.ID, "c2")
    c3 = driver.find_element(By.ID, "c3")
    c4 = driver.find_element(By.ID, "c4")
    c5 = driver.find_element(By.ID, "c5")
    c6 = driver.find_element(By.ID, "c6")
    c7 = driver.find_element(By.ID, "c7")
    l1 = driver.find_element(By.ID, "l1")
    l2 = driver.find_element(By.ID, "l2")
    l3 = driver.find_element(By.ID, "l3")
    l4 = driver.find_element(By.ID, "l4")
    s1 = driver.find_element(By.ID, "s1")
    s2 = driver.find_element(By.ID, "s2")
    s3 = driver.find_element(By.ID, "s3")
    c1s = driver.find_element(By.ID, "c1s")
    l1s = driver.find_element(By.ID, "l1s")
    s1s = driver.find_element(By.ID, "s1s")

    # assert on defaults where present
    assert c1.text == ""
    assert c2.text == "c2 default"
    assert c3.text == ""
    assert c4.text == ""
    assert c5.text == ""
    assert c6.text == ""
    assert c7.text == "c7 default"
    assert l1.text == ""
    assert l2.text == "l2 default"
    assert l3.text == ""
    assert l4.text == "l4 default"
    assert s1.text == ""
    assert s2.text == "s2 default"
    assert s3.text == ""
    assert c1s.text == ""
    assert l1s.text == ""
    assert s1s.text == ""

    # no cookies should be set yet!
    assert not driver.get_cookies()
    local_storage_items = local_storage.items()
    local_storage_items.pop("last_compiled_time", None)
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

    state_name = client_side.get_full_state_name(["_client_side_state"])
    sub_state_name = client_side.get_full_state_name(
        ["_client_side_state", "_client_side_sub_state"]
    )
    sub_sub_state_name = client_side.get_full_state_name(
        ["_client_side_state", "_client_side_sub_state", "_client_side_sub_sub_state"]
    )

    exp_cookies = {
        f"{sub_state_name}.c1": {
            "domain": "localhost",
            "httpOnly": False,
            "name": f"{sub_state_name}.c1",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "c1%20value",
        },
        f"{sub_state_name}.c2": {
            "domain": "localhost",
            "httpOnly": False,
            "name": f"{sub_state_name}.c2",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "c2%20value",
        },
        f"{sub_state_name}.c4": {
            "domain": "localhost",
            "httpOnly": False,
            "name": f"{sub_state_name}.c4",
            "path": "/",
            "sameSite": "Strict",
            "secure": False,
            "value": "c4%20value",
        },
        "c6": {
            "domain": "localhost",
            "httpOnly": False,
            "name": "c6",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "c6%20value",
        },
        f"{sub_state_name}.c7": {
            "domain": "localhost",
            "httpOnly": False,
            "name": f"{sub_state_name}.c7",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "c7%20value",
        },
        f"{sub_sub_state_name}.c1s": {
            "domain": "localhost",
            "httpOnly": False,
            "name": f"{sub_sub_state_name}.c1s",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "c1s%20value",
        },
    }
    AppHarness._poll_for(
        lambda: all(cookie_key in cookie_info_map(driver) for cookie_key in exp_cookies)
    )
    cookies = cookie_info_map(driver)
    for exp_cookie_key, exp_cookie_data in exp_cookies.items():
        assert cookies.pop(exp_cookie_key) == exp_cookie_data
    # assert all cookies have been popped for this page
    assert not cookies

    # Test cookie with expiry by itself to avoid timing flakiness
    set_sub("c3", "c3 value")
    AppHarness._poll_for(lambda: f"{sub_state_name}.c3" in cookie_info_map(driver))
    c3_cookie = cookie_info_map(driver)[f"{sub_state_name}.c3"]
    assert c3_cookie.pop("expiry") is not None
    assert c3_cookie == {
        "domain": "localhost",
        "httpOnly": False,
        "name": f"{sub_state_name}.c3",
        "path": "/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c3%20value",
    }
    time.sleep(2)  # wait for c3 to expire
    if not isinstance(driver, Firefox):
        # Note: Firefox does not remove expired cookies Bug 576347
        assert f"{sub_state_name}.c3" not in cookie_info_map(driver)

    local_storage_items = local_storage.items()
    local_storage_items.pop("last_compiled_time", None)
    assert local_storage_items.pop(f"{sub_state_name}.l1") == "l1 value"
    assert local_storage_items.pop(f"{sub_state_name}.l2") == "l2 value"
    assert local_storage_items.pop("l3") == "l3 value"
    assert local_storage_items.pop(f"{sub_state_name}.l4") == "l4 value"
    assert local_storage_items.pop(f"{sub_sub_state_name}.l1s") == "l1s value"
    assert not local_storage_items

    session_storage_items = session_storage.items()
    session_storage_items.pop("token", None)
    assert session_storage_items.pop(f"{sub_state_name}.s1") == "s1 value"
    assert session_storage_items.pop(f"{sub_state_name}.s2") == "s2 value"
    assert session_storage_items.pop("s3") == "s3 value"
    assert session_storage_items.pop(f"{sub_sub_state_name}.s1s") == "s1s value"
    assert not session_storage_items

    assert c1.text == "c1 value"
    assert c2.text == "c2 value"
    assert c3.text == "c3 value"
    assert c4.text == "c4 value"
    assert c5.text == "c5 value"
    assert c6.text == "c6 value"
    assert c7.text == "c7 value"
    assert l1.text == "l1 value"
    assert l2.text == "l2 value"
    assert l3.text == "l3 value"
    assert l4.text == "l4 value"
    assert s1.text == "s1 value"
    assert s2.text == "s2 value"
    assert s3.text == "s3 value"
    assert c1s.text == "c1s value"
    assert l1s.text == "l1s value"
    assert s1s.text == "s1s value"

    # navigate to the /foo route
    with utils.poll_for_navigation(driver):
        driver.get(client_side.frontend_url + "/foo")

    # get new references to all cookie and local storage elements
    c1 = driver.find_element(By.ID, "c1")
    c2 = driver.find_element(By.ID, "c2")
    c3 = driver.find_element(By.ID, "c3")
    c4 = driver.find_element(By.ID, "c4")
    c5 = driver.find_element(By.ID, "c5")
    c6 = driver.find_element(By.ID, "c6")
    c7 = driver.find_element(By.ID, "c7")
    l1 = driver.find_element(By.ID, "l1")
    l2 = driver.find_element(By.ID, "l2")
    l3 = driver.find_element(By.ID, "l3")
    l4 = driver.find_element(By.ID, "l4")
    s1 = driver.find_element(By.ID, "s1")
    s2 = driver.find_element(By.ID, "s2")
    s3 = driver.find_element(By.ID, "s3")
    c1s = driver.find_element(By.ID, "c1s")
    l1s = driver.find_element(By.ID, "l1s")
    s1s = driver.find_element(By.ID, "s1s")

    assert c1.text == "c1 value"
    assert c2.text == "c2 value"
    assert c3.text == ""  # cookie expired so value removed from state
    assert c4.text == "c4 value"
    assert c5.text == "c5 value"
    assert c6.text == "c6 value"
    assert c7.text == "c7 value"
    assert l1.text == "l1 value"
    assert l2.text == "l2 value"
    assert l3.text == "l3 value"
    assert l4.text == "l4 value"
    assert s1.text == "s1 value"
    assert s2.text == "s2 value"
    assert s3.text == "s3 value"
    assert c1s.text == "c1s value"
    assert l1s.text == "l1s value"
    assert s1s.text == "s1s value"

    # reset the backend state to force refresh from client storage
    async with client_side.modify_state(f"{token}_{state_name}") as state:
        state.reset()
    driver.refresh()

    # wait for the backend connection to send the token (again)
    token_input = driver.find_element(By.ID, "token")
    assert token_input
    token = client_side.poll_for_value(token_input)
    assert token is not None

    # get new references to all cookie and local storage elements (again)
    c1 = driver.find_element(By.ID, "c1")
    c2 = driver.find_element(By.ID, "c2")
    c3 = driver.find_element(By.ID, "c3")
    c4 = driver.find_element(By.ID, "c4")
    c5 = driver.find_element(By.ID, "c5")
    c6 = driver.find_element(By.ID, "c6")
    c7 = driver.find_element(By.ID, "c7")
    l1 = driver.find_element(By.ID, "l1")
    l2 = driver.find_element(By.ID, "l2")
    l3 = driver.find_element(By.ID, "l3")
    l4 = driver.find_element(By.ID, "l4")
    s1 = driver.find_element(By.ID, "s1")
    s2 = driver.find_element(By.ID, "s2")
    s3 = driver.find_element(By.ID, "s3")
    c1s = driver.find_element(By.ID, "c1s")
    l1s = driver.find_element(By.ID, "l1s")
    s1s = driver.find_element(By.ID, "s1s")

    assert c1.text == "c1 value"
    assert c2.text == "c2 value"
    assert c3.text == ""  # temporary cookie expired after reset state!
    assert c4.text == "c4 value"
    assert c5.text == "c5 value"
    assert c6.text == "c6 value"
    assert c7.text == "c7 value"
    assert l1.text == "l1 value"
    assert l2.text == "l2 value"
    assert l3.text == "l3 value"
    assert l4.text == "l4 value"
    assert s1.text == "s1 value"
    assert s2.text == "s2 value"
    assert s3.text == "s3 value"
    assert c1s.text == "c1s value"
    assert l1s.text == "l1s value"
    assert s1s.text == "s1s value"

    # make sure c5 cookie shows up on the `/foo` route
    AppHarness._poll_for(lambda: f"{sub_state_name}.c5" in cookie_info_map(driver))
    assert cookie_info_map(driver)[f"{sub_state_name}.c5"] == {
        "domain": "localhost",
        "httpOnly": False,
        "name": f"{sub_state_name}.c5",
        "path": "/foo/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c5%20value",
    }

    # Open a new tab to check that sync'd local storage is working
    main_tab = driver.window_handles[0]
    driver.switch_to.new_window("window")
    driver.get(client_side.frontend_url)

    # New tab should have a different state token.
    assert poll_for_token() != token

    # Set values and check them in the new tab.
    set_sub("l5", "l5 value")
    set_sub("l6", "l6 value")
    l5 = driver.find_element(By.ID, "l5")
    l6 = driver.find_element(By.ID, "l6")
    assert AppHarness._poll_for(lambda: l6.text == "l6 value")
    assert l5.text == "l5 value"

    # Set session storage values in the new tab
    set_sub("s1", "other tab s1")
    s1 = driver.find_element(By.ID, "s1")
    s2 = driver.find_element(By.ID, "s2")
    s3 = driver.find_element(By.ID, "s3")
    assert AppHarness._poll_for(lambda: s1.text == "other tab s1")
    assert s2.text == "s2 default"
    assert s3.text == ""

    # Switch back to main window.
    driver.switch_to.window(main_tab)

    # The values should have updated automatically.
    l5 = driver.find_element(By.ID, "l5")
    l6 = driver.find_element(By.ID, "l6")
    assert AppHarness._poll_for(lambda: l6.text == "l6 value")
    assert l5.text == "l5 value"

    s1 = driver.find_element(By.ID, "s1")
    s2 = driver.find_element(By.ID, "s2")
    s3 = driver.find_element(By.ID, "s3")
    assert AppHarness._poll_for(lambda: s1.text == "s1 value")
    assert s2.text == "s2 value"
    assert s3.text == "s3 value"

    # clear the cookie jar and local storage, ensure state reset to default
    driver.delete_all_cookies()
    local_storage.clear()

    # refresh the page to trigger re-hydrate
    driver.refresh()

    # wait for the backend connection to send the token (again)
    token_input = driver.find_element(By.ID, "token")
    assert token_input
    token = client_side.poll_for_value(token_input)
    assert token is not None

    # all values should be back to their defaults
    c1 = driver.find_element(By.ID, "c1")
    c2 = driver.find_element(By.ID, "c2")
    c3 = driver.find_element(By.ID, "c3")
    c4 = driver.find_element(By.ID, "c4")
    c5 = driver.find_element(By.ID, "c5")
    c6 = driver.find_element(By.ID, "c6")
    c7 = driver.find_element(By.ID, "c7")
    l1 = driver.find_element(By.ID, "l1")
    l2 = driver.find_element(By.ID, "l2")
    l3 = driver.find_element(By.ID, "l3")
    l4 = driver.find_element(By.ID, "l4")
    c1s = driver.find_element(By.ID, "c1s")
    l1s = driver.find_element(By.ID, "l1s")

    # assert on defaults where present
    assert c1.text == ""
    assert c2.text == "c2 default"
    assert c3.text == ""
    assert c4.text == ""
    assert c5.text == ""
    assert c6.text == ""
    assert c7.text == "c7 default"
    assert l1.text == ""
    assert l2.text == "l2 default"
    assert l3.text == ""
    assert l4.text == "l4 default"
    assert c1s.text == ""
    assert l1s.text == ""
