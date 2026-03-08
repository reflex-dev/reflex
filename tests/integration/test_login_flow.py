"""Integration tests for client side storage."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from reflex.constants.state import FIELD_MARKER
from reflex.testing import AppHarness

from . import utils


def LoginSample():
    """Sample app for testing login/logout with LocalStorage var."""
    import reflex as rx

    class State(rx.State):
        auth_token: str = rx.LocalStorage("")

        @rx.event
        def set_auth_token(self, token: str):
            self.auth_token = token

        @rx.event
        def logout(self):
            self.set_auth_token("")

        @rx.event
        def login(self):
            self.set_auth_token("12345")
            yield rx.redirect("/")

    def index():
        return rx.cond(  # pyright: ignore [reportCallIssue]
            State.is_hydrated & State.auth_token,  # pyright: ignore [reportOperatorIssue]
            rx.vstack(
                rx.heading(State.auth_token, id="auth-token"),
                rx.button("Logout", on_click=State.logout, id="logout"),
            ),
            rx.button("Login", on_click=rx.redirect("/login"), id="login"),
        )

    def login():
        return rx.vstack(
            rx.button("Do it", on_click=State.login, id="doit"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(login)


@pytest.fixture(scope="module")
def login_sample(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start LoginSample app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("login_sample"),
        app_source=LoginSample,
    ) as harness:
        yield harness


@pytest.fixture
def driver(login_sample: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the login_sample app.

    Args:
        login_sample: harness for LoginSample app

    Yields:
        WebDriver instance.
    """
    assert login_sample.app_instance is not None, "app is not running"
    driver = login_sample.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture
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


def test_login_flow(
    login_sample: AppHarness, driver: WebDriver, local_storage: utils.LocalStorage
):
    """Test login flow.

    Args:
        login_sample: harness for LoginSample app.
        driver: WebDriver instance.
        local_storage: Local storage helper.
    """
    assert login_sample.frontend_url is not None
    local_storage.clear()

    login_button = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "login")
    )
    with pytest.raises(NoSuchElementException):
        driver.find_element(By.ID, "auth-token")

    login_sample.poll_for_content(login_button)
    with utils.poll_for_navigation(driver):
        login_button.click()
    assert driver.current_url.endswith("/login")

    do_it_button = driver.find_element(By.ID, "doit")
    with utils.poll_for_navigation(driver):
        do_it_button.click()
    assert driver.current_url == login_sample.frontend_url

    def check_auth_token_header():
        try:
            auth_token_header = driver.find_element(By.ID, "auth-token")
        except NoSuchElementException:
            return False
        return auth_token_header.text

    assert AppHarness.poll_for_or_raise_timeout(check_auth_token_header) == "12345"

    logout_button = driver.find_element(By.ID, "logout")
    logout_button.click()

    state_name = login_sample.get_full_state_name(["_state"])
    AppHarness.expect(
        lambda: local_storage[f"{state_name}.auth_token" + FIELD_MARKER] == ""
    )
    with pytest.raises(NoSuchElementException):
        driver.find_element(By.ID, "auth-token")
