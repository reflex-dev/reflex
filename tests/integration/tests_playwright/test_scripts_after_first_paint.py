"""A prerendered page starts its scripts after its first paint, and still hydrates."""

import json
import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

import reflex.constants as constants
import reflex.utils.prerequisites as prerequisites
from reflex.testing import AppHarness, AppHarnessProd
from reflex.utils.misc import preload_color_theme

HYDRATED = """() => Object.keys(document.getElementById("increment")).some(
    (key) => key.startsWith("__reactProps$")
)"""

# Keeps the page from learning that it painted, and drops the timeout that
# covers for that (FIRST_PAINT_TIMEOUT_MS in utils/scripts.js), while the
# document is parsed: only an input is left to start the scripts.
NEVER_PAINTED = """
PerformanceObserver.prototype.observe = function () {};
const setTimeout_ = window.setTimeout;
window.setTimeout = (handler, delay, ...args) =>
    delay === 1000 ? 0 : setTimeout_(handler, delay, ...args);
document.addEventListener("DOMContentLoaded", () => {
    window.setTimeout = setTimeout_;
});
"""


def ScriptsAfterFirstPaintApp():
    """App with prerendered pages and a page that is rendered in the browser."""
    import reflex as rx

    class CounterState(rx.State):
        count: int = 0

        @rx.event
        def increment(self):
            self.count += 1

    def counter(heading: rx.Component, *links: rx.Component) -> rx.Component:
        return rx.el.main(
            heading,
            rx.el.p(CounterState.count, id="count"),
            rx.el.button("Increment", id="increment", on_click=CounterState.increment),
            *links,
        )

    def index():
        return counter(rx.el.h1("Index"), rx.link("Other", href="/other"))

    def other():
        return counter(rx.el.h1("Other"))

    def post():
        return counter(rx.el.h1("Post ", rx.State.post_id))  # pyright: ignore [reportAttributeAccessIssue]

    app = rx.App()
    app.add_page(index, title="Index")
    app.add_page(other, title="Other")
    app.add_page(post, route="/post/[post_id]", title="Post")


@pytest.fixture(scope="module")
def scripts_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the app in dev or production mode.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("scripts_after_first_paint"),
        app_name=f"scriptsafterfirstpaint_{app_harness_env.__name__.lower()}",
        app_source=ScriptsAfterFirstPaintApp,
    ) as harness:
        yield harness


def _frontend_url(harness: AppHarness) -> str:
    """Get the frontend URL of a running harness.

    Args:
        harness: The running app harness.

    Returns:
        The URL, without a trailing slash.
    """
    assert harness.frontend_url is not None
    return harness.frontend_url.rstrip("/")


def test_prerendered_head_preloads_no_script(scripts_app: AppHarness):
    """The head of a prerendered page holds the stylesheet and no module preload."""
    if not isinstance(scripts_app, AppHarnessProd):
        pytest.skip("pages are prerendered in prod only")
    static_dir = (
        scripts_app.app_path / prerequisites.get_web_dir() / constants.Dirs.STATIC
    )
    html = (static_dir / "index.html").read_text()
    head = html[html.index("<head>") : html.index("</head>") + len("</head>")]
    theme_script = json.loads(
        preload_color_theme("system").render()["children"][0]["contents"]
    )
    stylesheet = "/assets/__reflex_global_styles-HASH.css"
    assert re.sub(r"-[\w-]{8}\.css", "-HASH.css", head) == (
        '<head><meta charSet="utf-8"/>'
        '<meta content="width=device-width, initial-scale=1" name="viewport"/>'
        f'<link as="style" href="{stylesheet}" rel="preload"/>'
        "<title>Index</title>"
        '<meta content="favicon.ico" property="og:image"/>'
        f"<script>{theme_script}</script>"
        f'<link href="{stylesheet}" rel="stylesheet" type="text/css"/></head>'
    )


def test_pages_hydrate_and_handle_events(scripts_app: AppHarness, page: Page):
    """Prerendered, client-navigated and client-rendered pages all handle a click."""
    frontend_url = _frontend_url(scripts_app)
    problems: list[str] = []
    page.on(
        "console",
        lambda message: (
            problems.append(f"{message.type}: {message.text}")
            if message.type in {"warning", "error"}
            else None
        ),
    )
    page.on("pageerror", lambda error: problems.append(f"pageerror: {error}"))
    count = page.locator("#count")
    increment = page.get_by_role("button", name="Increment")

    # A prerendered page in prod.
    page.goto(frontend_url)
    expect(page.get_by_role("heading", name="Index")).to_be_visible()
    page.wait_for_function(HYDRATED)
    increment.click()
    expect(count).to_have_text("1")

    # A client-side navigation.
    page.get_by_role("link", name="Other").click()
    expect(page.get_by_role("heading", name="Other")).to_be_visible()
    increment.click()
    expect(count).to_have_text("2")

    # A dynamic route, which is rendered in the browser.
    page.goto(f"{frontend_url}/post/7")
    expect(page.get_by_role("heading", name="Post 7")).to_be_visible()
    increment.click()
    expect(count).to_have_text("3")

    assert problems == []


def test_input_before_first_paint_starts_scripts(scripts_app: AppHarness, page: Page):
    """A click on a page that cannot handle one yet starts its scripts and is not lost."""
    if not isinstance(scripts_app, AppHarnessProd):
        pytest.skip("pages are prerendered in prod only")
    page.add_init_script(NEVER_PAINTED)
    page.goto(_frontend_url(scripts_app), wait_until="load")
    modules = page.locator('head script[type="module"]')
    increment = page.get_by_role("button", name="Increment")
    expect(increment).to_be_visible()
    assert modules.count() == 0
    assert not page.evaluate(HYDRATED)

    # No handler is attached yet: the click is dispatched again after hydration.
    increment.click()
    assert modules.count() == 1
    expect(page.locator("#count")).to_have_text("1")
    increment.click()
    expect(page.locator("#count")).to_have_text("2")
