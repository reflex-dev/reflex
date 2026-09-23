"""Integration tests for ``rx._x.client_state`` shared between sibling components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ClientStateApp():
    """App sharing a global client state var between sibling components."""
    import reflex as rx

    class ClientStateAppState(rx.State):
        show: bool = False

        @rx.event
        def reveal(self):
            self.show = True

    shared = rx._x.client_state(default="initial")

    def index():
        return rx.box(
            rx.button("set", on_click=shared.set_value("clicked"), id="setter"),
            rx.button("reveal", on_click=ClientStateAppState.reveal, id="reveal"),
            rx.cond(
                ClientStateAppState.show,
                rx.text(shared.value, id="late-reader"),
            ),
            rx.text(ClientStateAppState.router.session.client_token, id="token"),
        )

    def siblings():
        return rx.box(
            rx.text(shared.value, id="reader"),
            rx.button("set", on_click=shared.set_value("clicked"), id="setter"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(siblings)


@pytest.fixture(scope="module")
def client_state_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the client state app under an AppHarness.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_state"),
        app_source=ClientStateApp,
    ) as harness:
        yield harness


def _collect_page_errors(page: Page) -> list[str]:
    """Record uncaught frontend errors raised on the page.

    Args:
        page: Playwright page.

    Returns:
        A list that is appended to as errors occur.
    """
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors


def test_sibling_setter_updates_reader(
    client_state_app: AppHarness, page: Page
) -> None:
    """A sibling button setting the client state updates the sibling reader.

    Args:
        client_state_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_app.frontend_url is not None
    errors = _collect_page_errors(page)
    page.goto(client_state_app.frontend_url.removesuffix("/") + "/siblings")

    expect(page.locator("#reader")).to_have_text("initial")
    page.click("#setter")
    expect(page.locator("#reader")).to_have_text("clicked")
    assert errors == []


def test_setter_works_before_reader_mounts(
    client_state_app: AppHarness, page: Page
) -> None:
    """The setter works even when no component reading the value is mounted.

    Args:
        client_state_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_app.frontend_url is not None
    errors = _collect_page_errors(page)
    page.goto(client_state_app.frontend_url)
    expect(page.locator("#token")).not_to_be_empty()

    page.click("#setter")
    page.click("#reveal")
    expect(page.locator("#late-reader")).to_have_text("clicked")
    assert errors == []
