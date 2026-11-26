"""Integration tests for a stateless app."""

from collections.abc import Generator
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.sync_api import ConsoleMessage, Page, WebSocket, expect
from reflex_base.config import get_config
from reflex_base.constants import Endpoint

from reflex.testing import AppHarness


def StatelessApp():
    """A stateless app with client state, scripts and links."""
    import reflex as rx

    menu = rx.client_state(False)

    def index():
        return rx.el.div(
            rx.heading("This is a stateless app"),
            rx.el.button("Menu", id="menu-toggle", on_click=menu.set(~menu.value)),
            rx.cond(menu.value, rx.el.nav("Menu open", id="menu")),
            rx.el.input(id="function-output"),
            rx.el.button(
                "Function",
                id="call-function",
                on_click=rx.call_function(
                    "() => 6 * 7",
                    callback=lambda result: rx.set_value("function-output", result),
                ),
            ),
            rx.el.input(id="script-output"),
            rx.el.button(
                "Script",
                id="call-script",
                on_click=rx.call_script(
                    "'script ' + typeof navigate",
                    callback=lambda result: rx.set_value("script-output", result),
                ),
            ),
            rx.link("Next", href="/next", id="next-link"),
            rx.el.button("Redirect", id="redirect", on_click=rx.redirect("/next")),
        )

    def next_page():
        return rx.heading("Next page", id="next-heading")

    app = rx.App(enable_state=False)
    app.add_page(index)
    app.add_page(next_page, route="/next")


@pytest.fixture(scope="module")
def stateless_app(
    app_harness_env: type[AppHarness], tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Create a dev or prod harness for the stateless app.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        AppHarness: A harness for testing the stateless app.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("stateless_app"),
        app_name=f"statelessapp_{app_harness_env.__name__.lower()}",
        app_source=StatelessApp,
    ) as harness:
        yield harness


def test_statelessness(stateless_app: AppHarness, page: Page):
    """Test that the stateless app renders a heading but backend/_event is not mounted.

    Args:
        stateless_app: A harness for testing the stateless app.
        page: A Playwright page.
    """
    assert stateless_app.frontend_url is not None
    assert stateless_app.backend is not None
    assert stateless_app.backend.started

    config = get_config()
    res = httpx.get(config.api_url + config.prepend_backend_path(str(Endpoint.EVENT)))
    assert res.status_code == 404

    res2 = httpx.get(Endpoint.PING.get_url())
    assert res2.status_code == 200

    page.goto(stateless_app.frontend_url)
    expect(page.get_by_role("heading")).to_have_text("This is a stateless app")


def test_frontend_events_run_without_a_connection(
    stateless_app: AppHarness, page: Page
):
    """Client state, scripts with callbacks, links and redirects work, and nothing connects.

    Args:
        stateless_app: A harness for testing the stateless app.
        page: A Playwright page.
    """
    assert stateless_app.frontend_url is not None
    # The dev server's own hot reload socket is not the backend's.
    backend = urlsplit(get_config().api_url).port
    websockets: list[str] = []
    errors: list[str] = []

    def on_websocket(websocket: WebSocket):
        if urlsplit(websocket.url).port == backend:
            websockets.append(websocket.url)

    def on_console(message: ConsoleMessage):
        if message.type == "error":
            errors.append(message.text)

    page.on("websocket", on_websocket)
    page.on("console", on_console)

    page.goto(stateless_app.frontend_url)
    toggle = page.locator("#menu-toggle")
    expect(toggle).to_be_visible()

    toggle.click()
    expect(page.locator("#menu")).to_have_text("Menu open")
    toggle.click()
    expect(page.locator("#menu")).to_have_count(0)

    # Compiled callbacks are strings that call ReflexEvent and addEvents.
    page.locator("#call-function").click()
    expect(page.locator("#function-output")).to_have_value("42")
    page.locator("#call-script").click()
    expect(page.locator("#script-output")).to_have_value("script function")

    page.locator("#next-link").click()
    expect(page.locator("#next-heading")).to_have_text("Next page")
    page.go_back()
    page.locator("#redirect").click()
    expect(page.locator("#next-heading")).to_have_text("Next page")

    assert websockets == []
    assert errors == []
