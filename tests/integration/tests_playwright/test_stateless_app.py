"""Integration tests for a stateless app."""

from collections.abc import Generator
from urllib.parse import urlsplit

import httpx2
import pytest
from playwright.sync_api import Page, expect
from reflex_base.config import get_config
from reflex_base.constants import Endpoint

from reflex.testing import AppHarness, AppHarnessProd
from tests.integration.utils import built_scripts, libraries_in_scripts, record_scripts


def StatelessApp():
    """A stateless app whose events all run in the browser."""
    import reflex as rx

    counter = rx.client_state(0, name="counter")

    def index():
        return rx.el.div(
            rx.heading("This is a stateless app"),
            rx.el.input(id="field"),
            rx.el.p(id="script-output"),
            rx.el.button(
                "Run script",
                id="run-script",
                on_click=rx.call_script(
                    "document.getElementById('script-output').textContent ="
                    " 'stored: ' + localStorage.getItem('stateless-key')"
                ),
            ),
            rx.el.button(
                "Fill", id="fill", on_click=rx.set_value("field", "filled in")
            ),
            rx.el.button(
                "Forget",
                id="forget",
                on_click=[
                    rx.remove_cookie("stateless-cookie"),
                    rx.remove_local_storage("stateless-key"),
                ],
            ),
            rx.el.button(
                counter.value, id="count", on_click=counter.set(lambda v: v + 1)
            ),
            rx.el.button("Toggle", id="toggle", on_click=rx.toggle_color_mode),
            rx.el.button("Go", id="go", on_click=rx.redirect("/other")),
            rx.link("Other page", href="/other", id="link"),
        )

    def other():
        return rx.el.div(
            rx.heading("The other page"),
            rx.el.button("Back", id="back", on_click=rx.redirect("/")),
        )

    app = rx.App(enable_state=False)
    app.add_page(index)
    app.add_page(other, route="/other")


@pytest.fixture(scope="module")
def stateless_app(
    app_harness_env: type[AppHarness], tmp_path_factory
) -> Generator[AppHarness, None, None]:
    """Create a stateless app AppHarness.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        AppHarness: A harness for testing the stateless app.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("stateless_app"),
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
    res = httpx2.get(config.api_url + config.prepend_backend_path(str(Endpoint.EVENT)))
    assert res.status_code == 404

    res2 = httpx2.get(Endpoint.PING.get_url())
    assert res2.status_code == 200

    page.goto(stateless_app.frontend_url)
    expect(page.get_by_role("heading")).to_have_text("This is a stateless app")


def test_stateless_app_runs_without_the_state_runtime(
    stateless_app: AppHarness, page: Page
):
    """The page loads no socket, cookie library or toaster, and its events still run.

    Args:
        stateless_app: A harness for testing the stateless app.
        page: A Playwright page.
    """
    assert stateless_app.frontend_url is not None
    websockets: list[str] = []
    page_errors: list[str] = []
    page.on("websocket", lambda ws: websockets.append(ws.url))
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    scripts = record_scripts(page)

    page.goto(stateless_app.frontend_url)
    expect(page.get_by_role("heading")).to_have_text("This is a stateless app")
    page.evaluate(
        "() => { localStorage.setItem('stateless-key', 'kept');"
        " document.cookie = 'stateless-cookie=1; path=/'; }"
    )

    # A script reads browser storage.
    page.locator("#run-script").click()
    expect(page.locator("#script-output")).to_have_text("stored: kept")

    # Refs, cookies and local storage.
    page.locator("#fill").click()
    expect(page.locator("#field")).to_have_value("filled in")
    page.locator("#forget").click()
    page.locator("#run-script").click()
    expect(page.locator("#script-output")).to_have_text("stored: null")
    assert page.evaluate("() => document.cookie") == ""

    # Client state.
    expect(page.locator("#count")).to_have_text("0")
    page.locator("#count").click()
    page.locator("#count").click()
    expect(page.locator("#count")).to_have_text("2")

    # Color mode.
    initial_mode = page.evaluate("() => document.documentElement.className")
    assert initial_mode in ("light", "dark")
    page.locator("#toggle").click()
    expect(page.locator("html")).to_have_class(
        "dark" if initial_mode == "light" else "light"
    )

    # Navigation, by event and by link.
    page.locator("#go").click()
    expect(page.get_by_role("heading")).to_have_text("The other page")
    page.locator("#back").click()
    expect(page.get_by_role("heading")).to_have_text("This is a stateless app")
    page.locator("#link").click()
    expect(page.get_by_role("heading")).to_have_text("The other page")

    # There is no backend to lose: nothing reports a connection error.
    expect(page.locator("[title^='Connection Error']")).to_have_count(0)
    expect(page.get_by_text("Cannot connect to server")).to_have_count(0)

    assert page_errors == []
    # The dev server's own hot-reload socket, to the frontend, is the only one.
    frontend = urlsplit(stateless_app.frontend_url).netloc
    assert [url for url in websockets if urlsplit(url).netloc != frontend] == []
    if isinstance(stateless_app, AppHarnessProd):
        assert websockets == []
    assert scripts
    assert libraries_in_scripts(scripts) == {
        "socket.io": False,
        "universal-cookie": False,
        "sonner": False,
    }


def test_stateless_build_contains_no_state_runtime(stateless_app: AppHarness):
    """No chunk of the production build holds socket.io, the cookie library or the toaster.

    Args:
        stateless_app: A harness for testing the stateless app.
    """
    if not isinstance(stateless_app, AppHarnessProd):
        pytest.skip("only a production build is bundled")
    scripts = built_scripts(stateless_app)
    assert scripts
    assert libraries_in_scripts(scripts) == {
        "socket.io": False,
        "universal-cookie": False,
        "sonner": False,
    }
