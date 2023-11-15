"""Integration tests for client side storage."""
from __future__ import annotations

from typing import Generator

import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from nextpy.core.testing import AppHarness

from . import utils



def LoginSample():
    """Sample app for testing login/logout with LocalStorage var."""
    import nextpy as xt

    class State(xt.State):
        auth_token: str = xt.LocalStorage("")

        def logout(self):
            self.set_auth_token("")

        def login(self):
            self.set_auth_token("12345")
            yield xt.redirect("/")

    def index():
        return xt.Cond.create(
            State.is_hydrated & State.auth_token,  # type: ignore
            xt.vstack(
                xt.heading(State.auth_token, id="auth-token"),
                xt.button("Logout", on_click=State.logout, id="logout"),
            ),
            xt.button("Login", on_click=xt.redirect("/login"), id="login"),
        )

    def login():
        return xt.vstack(
            xt.button("Do it", on_click=State.login, id="doit"),
        )

    app = xt.App(state=State)
    app.add_page(index)
    app.add_page(login)
    app.compile()


@pytest.fixture(scope="session")
def login_sample(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start LoginSample app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("login_sample"),
        app_source=LoginSample,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture()
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

    with pytest.raises(NoSuchElementException):
        driver.find_element(By.ID, "auth-token")

    login_button = driver.find_element(By.ID, "login")
    login_sample.poll_for_content(login_button)
    with utils.poll_for_navigation(driver):
        login_button.click()
    assert driver.current_url.endswith("/login/")

    do_it_button = driver.find_element(By.ID, "doit")
    with utils.poll_for_navigation(driver):
        do_it_button.click()
    assert driver.current_url == login_sample.frontend_url + "/"

    def check_auth_token_header():
        try:
            auth_token_header = driver.find_element(By.ID, "auth-token")
        except NoSuchElementException:
            return False
        return auth_token_header.text

    assert login_sample._poll_for(check_auth_token_header) == "12345"

    logout_button = driver.find_element(By.ID, "logout")
    logout_button.click()

    assert login_sample._poll_for(lambda: local_storage["state.auth_token"] == "")
    with pytest.raises(NoSuchElementException):
        driver.find_element(By.ID, "auth-token")