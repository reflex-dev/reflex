"""Integration tests for client side storage."""
from __future__ import annotations

import time
from typing import Generator

import pytest
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

        @rx.var
        def token(self) -> str:
            return self.get_token()

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

        def set_var(self):
            setattr(self, self.state_var, self.input_value)
            self.state_var = self.input_value = ""

    class ClientSideSubSubState(ClientSideSubState):
        c1s: str = rx.Cookie()
        l1s: str = rx.LocalStorage()

        def set_var(self):
            setattr(self, self.state_var, self.input_value)
            self.state_var = self.input_value = ""

    def index():
        return rx.fragment(
            rx.input(value=ClientSideState.token, is_read_only=True, id="token"),
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
            rx.box(ClientSideSubSubState.c1s, id="c1s"),
            rx.box(ClientSideSubSubState.l1s, id="l1s"),
        )

    app = rx.App(state=ClientSideState)
    app.add_page(index)
    app.add_page(index, route="/foo")
    app.compile()


@pytest.fixture(scope="session")
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
        assert client_side.poll_for_clients()
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


def test_client_side_state(
    client_side: AppHarness, driver: WebDriver, local_storage: utils.LocalStorage
):
    """Test client side state.

    Args:
        client_side: harness for ClientSide app.
        driver: WebDriver instance.
        local_storage: Local storage helper.
    """
    assert client_side.app_instance is not None
    assert client_side.frontend_url is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = client_side.poll_for_value(token_input)
    assert token is not None

    backend_state = client_side.app_instance.state_manager.states[token]

    # get a reference to the cookie manipulation form
    state_var_input = driver.find_element(By.ID, "state_var")
    input_value_input = driver.find_element(By.ID, "input_value")
    set_sub_state_button = driver.find_element(By.ID, "set_sub_state")
    set_sub_sub_state_button = driver.find_element(By.ID, "set_sub_sub_state")

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

    # no cookies should be set yet!
    assert not driver.get_cookies()
    local_storage_items = local_storage.items()
    local_storage_items.pop("chakra-ui-color-mode", None)
    assert not local_storage_items

    # set some cookies and local storage values
    state_var_input.send_keys("c1")
    input_value_input.send_keys("c1 value")
    set_sub_state_button.click()
    state_var_input.send_keys("c2")
    input_value_input.send_keys("c2 value")
    set_sub_state_button.click()
    state_var_input.send_keys("c4")
    input_value_input.send_keys("c4 value")
    set_sub_state_button.click()
    state_var_input.send_keys("c5")
    input_value_input.send_keys("c5 value")
    set_sub_state_button.click()
    state_var_input.send_keys("c6")
    input_value_input.send_keys("c6 value")
    set_sub_state_button.click()
    state_var_input.send_keys("c7")
    input_value_input.send_keys("c7 value")
    set_sub_state_button.click()

    state_var_input.send_keys("l1")
    input_value_input.send_keys("l1 value")
    set_sub_state_button.click()
    state_var_input.send_keys("l2")
    input_value_input.send_keys("l2 value")
    set_sub_state_button.click()
    state_var_input.send_keys("l3")
    input_value_input.send_keys("l3 value")
    set_sub_state_button.click()
    state_var_input.send_keys("l4")
    input_value_input.send_keys("l4 value")
    set_sub_state_button.click()

    state_var_input.send_keys("c1s")
    input_value_input.send_keys("c1s value")
    set_sub_sub_state_button.click()
    state_var_input.send_keys("l1s")
    input_value_input.send_keys("l1s value")
    set_sub_sub_state_button.click()

    cookies = {cookie_info["name"]: cookie_info for cookie_info in driver.get_cookies()}
    assert cookies.pop("client_side_state.client_side_sub_state.c1") == {
        "domain": "localhost",
        "httpOnly": False,
        "name": "client_side_state.client_side_sub_state.c1",
        "path": "/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c1%20value",
    }
    assert cookies.pop("client_side_state.client_side_sub_state.c2") == {
        "domain": "localhost",
        "httpOnly": False,
        "name": "client_side_state.client_side_sub_state.c2",
        "path": "/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c2%20value",
    }
    assert cookies.pop("client_side_state.client_side_sub_state.c4") == {
        "domain": "localhost",
        "httpOnly": False,
        "name": "client_side_state.client_side_sub_state.c4",
        "path": "/",
        "sameSite": "Strict",
        "secure": False,
        "value": "c4%20value",
    }
    assert cookies.pop("c6") == {
        "domain": "localhost",
        "httpOnly": False,
        "name": "c6",
        "path": "/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c6%20value",
    }
    assert cookies.pop("client_side_state.client_side_sub_state.c7") == {
        "domain": "localhost",
        "httpOnly": False,
        "name": "client_side_state.client_side_sub_state.c7",
        "path": "/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c7%20value",
    }
    assert cookies.pop(
        "client_side_state.client_side_sub_state.client_side_sub_sub_state.c1s"
    ) == {
        "domain": "localhost",
        "httpOnly": False,
        "name": "client_side_state.client_side_sub_state.client_side_sub_sub_state.c1s",
        "path": "/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c1s%20value",
    }
    # assert all cookies have been popped for this page
    assert not cookies

    # Test cookie with expiry by itself to avoid timing flakiness
    state_var_input.send_keys("c3")
    input_value_input.send_keys("c3 value")
    set_sub_state_button.click()
    cookies = {cookie_info["name"]: cookie_info for cookie_info in driver.get_cookies()}
    c3_cookie = cookies["client_side_state.client_side_sub_state.c3"]
    assert c3_cookie.pop("expiry") is not None
    assert c3_cookie == {
        "domain": "localhost",
        "httpOnly": False,
        "name": "client_side_state.client_side_sub_state.c3",
        "path": "/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c3%20value",
    }
    time.sleep(2)  # wait for c3 to expire
    assert "client_side_state.client_side_sub_state.c3" not in {
        cookie_info["name"] for cookie_info in driver.get_cookies()
    }

    local_storage_items = local_storage.items()
    local_storage_items.pop("chakra-ui-color-mode", None)
    assert (
        local_storage_items.pop("client_side_state.client_side_sub_state.l1")
        == "l1 value"
    )
    assert (
        local_storage_items.pop("client_side_state.client_side_sub_state.l2")
        == "l2 value"
    )
    assert local_storage_items.pop("l3") == "l3 value"
    assert (
        local_storage_items.pop("client_side_state.client_side_sub_state.l4")
        == "l4 value"
    )
    assert (
        local_storage_items.pop(
            "client_side_state.client_side_sub_state.client_side_sub_sub_state.l1s"
        )
        == "l1s value"
    )
    assert not local_storage_items

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
    assert c1s.text == "c1s value"
    assert l1s.text == "l1s value"

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
    c1s = driver.find_element(By.ID, "c1s")
    l1s = driver.find_element(By.ID, "l1s")

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
    assert c1s.text == "c1s value"
    assert l1s.text == "l1s value"

    # reset the backend state to force refresh from client storage
    backend_state.reset()
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
    c1s = driver.find_element(By.ID, "c1s")
    l1s = driver.find_element(By.ID, "l1s")

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
    assert c1s.text == "c1s value"
    assert l1s.text == "l1s value"

    # make sure c5 cookie shows up on the `/foo` route
    cookies = {cookie_info["name"]: cookie_info for cookie_info in driver.get_cookies()}

    assert cookies["client_side_state.client_side_sub_state.c5"] == {
        "domain": "localhost",
        "httpOnly": False,
        "name": "client_side_state.client_side_sub_state.c5",
        "path": "/foo/",
        "sameSite": "Lax",
        "secure": False,
        "value": "c5%20value",
    }

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
