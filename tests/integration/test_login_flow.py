"""Integration tests for client side storage."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_base.constants.state import FIELD_MARKER

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
def local_storage(page: Page) -> Generator[utils.LocalStorage, None, None]:
    """Get an instance of the local storage helper.

    Args:
        page: Playwright Page instance.

    Yields:
        Local storage helper.
    """
    ls = utils.LocalStorage(page)
    yield ls
    ls.clear()


def test_login_flow(
    login_sample: AppHarness, page: Page, local_storage: utils.LocalStorage
):
    """Test login flow.

    Args:
        login_sample: harness for LoginSample app.
        page: Playwright Page instance.
        local_storage: Local storage helper.
    """
    assert login_sample.frontend_url is not None
    page.goto(login_sample.frontend_url)
    local_storage.clear()

    login_button = page.locator("#login")
    expect(page.locator("#auth-token")).to_have_count(0)

    with utils.poll_for_navigation(page):
        login_button.click()
    assert page.url.endswith("/login")

    do_it_button = page.locator("#doit")
    with utils.poll_for_navigation(page):
        do_it_button.click()
    assert page.url == login_sample.frontend_url

    auth_token_header = page.locator("#auth-token")
    expect(auth_token_header).to_have_text("12345")

    logout_button = page.locator("#logout")
    logout_button.click()

    state_name = login_sample.get_full_state_name(["_state"])
    AppHarness.expect(
        lambda: local_storage[f"{state_name}.auth_token" + FIELD_MARKER] == ""
    )
    expect(page.locator("#auth-token")).to_have_count(0)
