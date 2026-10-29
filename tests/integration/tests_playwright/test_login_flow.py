"""Integration tests for client-side storage."""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_base.constants.state import FIELD_MARKER

from reflex.testing import AppHarness


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
    """Start the LoginSample app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("login_sample"),
        app_source=LoginSample,
    ) as harness:
        yield harness


def test_login_flow(login_sample: AppHarness, page: Page) -> None:
    """Verify login and logout update the persisted client state."""
    assert login_sample.frontend_url is not None
    page.add_init_script("localStorage.clear()")
    page.goto(login_sample.frontend_url)

    login_button = page.locator("#login")
    expect(login_button).to_be_visible()
    expect(page.locator("#auth-token")).to_have_count(0)

    login_button.click()
    expect(page).to_have_url(re.compile(r"/login/?$"))
    page.locator("#doit").click()
    expect(page).to_have_url(re.compile(r"/$"))
    expect(page.locator("#auth-token")).to_have_text("12345")

    state_name = login_sample.get_full_state_name(["_state"])
    storage_key = f"{state_name}.auth_token{FIELD_MARKER}"
    page.locator("#logout").click()
    page.wait_for_function(
        "([key, expected]) => localStorage.getItem(key) === expected",
        arg=[storage_key, ""],
    )
    expect(page.locator("#auth-token")).to_have_count(0)
