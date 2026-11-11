"""Load every playground route in headless Chromium and fail on any page or console error.

It starts the playground for real (bun, node and network needed), in dev and in
prod mode, so it only runs when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/fixtures/test_playground_app.py``. With
``REFLEX_BENCH_NETWORK_TESTS=1`` as well, it also runs against reflex 0.8.23
from PyPI, on Python 3.12.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from reflex_bench import machine, subjects
from reflex_bench.context import Subject, subject_env, workspace_subject
from reflex_bench.drivers.app_process import AppProcess, cache_env
from reflex_bench.drivers.browser import HYDRATED, Browser, Tab
from reflex_bench.fixtures import materialize_playground, playground_dir

APP_TESTS = os.environ.get("REFLEX_BENCH_APP_TESTS") == "1"
SPECS = [
    "workspace",
    pytest.param(
        "0.8.23",
        marks=pytest.mark.skipif(
            os.environ.get("REFLEX_BENCH_NETWORK_TESTS") != "1",
            reason="installs reflex 0.8.23 from PyPI; set REFLEX_BENCH_NETWORK_TESTS=1",
        ),
    ),
]
# Every route of the playground, with the path the sweep loads for it.
ROUTES = {
    "/": "/",
    "/counter": "/counter",
    "/board": "/board",
    "/item/[item_id]": "/item/42",
    "/events": "/events",
    "/tasks": "/tasks",
    "/data": "/data",
    "/data/product/[product_id]": "/data/product/7",
    "/data/new": "/data/new",
    "/data/analytics": "/data/analytics",
    "/forms": "/forms",
    "/upload": "/upload",
    "/storage": "/storage",
    "/charts": "/charts",
    "/grids": "/grids",
    "/content": "/content",
    "/widgets": "/widgets",
    "/room/[room_id]": "/room/lobby",
    "/settings": "/settings",
    "/about": "/about",
    "404": "/no-such-page",
}
# The browser logs the 404 status of the page it was sent to. Reflex's prod
# server also answers a dynamic route with the 404 status and the app shell,
# whose router then renders the page (on the playground of main, /item/42 too).
NOT_FOUND = re.compile(
    r"^Failed to load resource: the server responded with a status of 404"
)
# Charts, grids and media render after hydration; on_load queries answer after it.
SETTLE_S = 2.0
# A dev server compiles each route on its first load.
HYDRATE_TIMEOUT_S = 60.0
SEED_PRODUCTS = 2000
_README_ROUTE = re.compile(r"^\| `(?P<route>[^`]+)` \|")


def _readme_routes() -> list[str]:
    """Read the route column of the playground README's page table.

    Returns:
        The routes, in table order.
    """
    text = (playground_dir() / "README.md").read_text(encoding="utf-8")
    pages = text.split("\n## Pages\n", 1)[1].split("\n## ", 1)[0]
    return [
        match["route"]
        for line in pages.splitlines()
        if (match := _README_ROUTE.match(line))
    ]


def test_the_readme_lists_every_route():
    assert _readme_routes() == list(ROUTES)


def _subject(spec: str, home: Path) -> Subject:
    """Build or reuse the environment of a subject.

    Args:
        spec: ``workspace`` or a version.
        home: The bench home holding subject venvs.

    Returns:
        The subject.
    """
    if spec == "workspace":
        return workspace_subject()
    return subjects.resolve(spec, python="3.12", home=home)


@pytest.fixture(scope="module")
def home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Share one bench home (venvs, bun) between the tests of the module.

    Returns:
        The bench home.
    """
    return tmp_path_factory.mktemp("home")


@contextlib.contextmanager
def _running_playground(
    tmp_path: Path, home: Path, spec: str, mode: str
) -> Iterator[AppProcess]:
    """Start a fresh copy of the playground.

    Args:
        tmp_path: Where the copy goes.
        home: The bench home holding subject venvs and bun.
        spec: ``workspace`` or a version.
        mode: ``dev`` or ``prod``.

    Yields:
        The app, HTTP-ready.
    """
    subject = _subject(spec, home)
    app_dir = tmp_path / "playground"
    materialize_playground(app_dir)
    env = {
        **subject_env(subject.python),
        **cache_env(
            reflex_dir=home / "reflex" / spec,
            web_dir=app_dir / ".web",
            states_dir=app_dir / ".states",
        ),
    }
    app = AppProcess(
        subject.python,
        app_dir,
        mode="dev" if mode == "dev" else "prod",
        reflex_version=subject.reflex_version,
        env=env,
        start_timeout=900,
    )
    try:
        app.start()
        app.wait_http_ready(timeout=300)
        yield app
    finally:
        app.stop()


NEEDS_APP = pytest.mark.skipif(
    not APP_TESTS, reason="starts the real playground; set REFLEX_BENCH_APP_TESTS=1"
)
NEEDS_CHROMIUM = pytest.mark.skipif(
    not machine._playwright_chromium(), reason="no Playwright chromium"
)


@pytest.mark.parametrize("mode", ["dev", "prod"])
@pytest.mark.parametrize("spec", SPECS)
@NEEDS_APP
@NEEDS_CHROMIUM
def test_every_route_loads_without_errors(
    tmp_path: Path, home: Path, spec: str, mode: str
):
    browser = Browser()
    problems: list[str] = []
    with _running_playground(tmp_path, home, spec, mode) as app:
        try:
            with urllib.request.urlopen(
                f"{app.backend_url}/api/playground/stats", timeout=30
            ) as response:
                assert json.load(response)["products"] == SEED_PRODUCTS
            browser.start()
            for route, path in ROUTES.items():
                tab = browser.new_page()
                messages: list[str] = []
                tab.page.on(
                    "console",
                    lambda message, messages=messages: (
                        messages.append(message.text)
                        if message.type == "error"
                        else None
                    ),
                )
                try:
                    tab.page.goto((app.frontend_url or app.backend_url) + path)
                    tab.page.wait_for_selector(
                        HYDRATED, state="attached", timeout=HYDRATE_TIMEOUT_S * 1000
                    )
                    tab.settle(SETTLE_S)
                except Exception as exc:
                    messages.append(f"not hydrated: {type(exc).__name__}: {exc}")
                finally:
                    browser.close_tab(tab)
                errors = list(tab.page_errors)
                not_found_ok = route == "404" or (mode == "prod" and "[" in route)
                errors.extend(
                    f"console: {text}"
                    for text in messages
                    if not (not_found_ok and NOT_FOUND.match(text))
                )
                if errors:
                    problems.append(f"{route} ({path}): {'; '.join(errors)}")
        finally:
            browser.close()
    assert not problems, "\n".join(problems)


def _open(tab: Tab, app: AppProcess, path: str) -> Page:
    """Open a playground page and wait until it is hydrated.

    Args:
        tab: The browser tab.
        app: The running playground.
        path: The page's path.

    Returns:
        The Playwright page.
    """
    tab.page.goto((app.frontend_url or app.backend_url) + path)
    tab.page.wait_for_selector(HYDRATED, state="attached")
    return tab.page


def _check_events(page: Page) -> None:
    """Fire every kind of event handler and check what each one logged.

    Args:
        page: The ``/events`` page.
    """
    total = page.locator("#events-total")
    page.click("#events-sync")
    expect(total).to_have_text("1")
    page.click("#events-args")
    expect(total).to_have_text("6")
    page.click("#events-async")
    expect(total).to_have_text("16")
    page.click("#events-chain")
    expect(page.locator("#events-log")).to_contain_text("chain: ended at 32")
    for button, entry in (
        ("#events-generator", "generator: done"),
        ("#events-background", "background: done"),
        ("#events-sibling", "sibling: read tasks"),
    ):
        page.click(button)
        expect(page.locator("#events-log")).to_contain_text(entry)
    page.click("#events-script")
    expect(page.locator("#events-script-result")).to_have_text(
        re.compile(r"title has \d+ characters")
    )


def _check_data(page: Page, app: AppProcess) -> None:
    """Filter, sort and page the product table, then create, edit and delete a product.

    Args:
        page: A page of the app.
        app: The running playground.
    """
    label = page.locator("#data-page")
    expect(label).to_have_text(f"Page 1 of 100 ({SEED_PRODUCTS} products)")
    page.click("#data-next")
    expect(label).to_have_text(f"Page 2 of 100 ({SEED_PRODUCTS} products)")
    page.fill("#data-filter", "Amber Anchor")
    expect(label).not_to_contain_text(f"{SEED_PRODUCTS} products")
    page.click("#data-sort-price-cents")
    expect(page.locator("#data-table")).to_contain_text("Amber Anchor")
    page.click("#data-reset")
    expect(label).to_have_text(f"Page 1 of 100 ({SEED_PRODUCTS} products)")

    page.goto((app.frontend_url or app.backend_url) + "/data/new")
    page.fill("#product-name", "x")
    # int() cannot parse a superscript digit, which str.isdigit() accepts.
    page.fill("#product-price-cents", "\u00b2")
    page.click("#product-save")
    expect(page.get_by_text("At least 3 characters.")).to_be_visible()
    expect(page.get_by_text("A whole number from 1 to 1000000.")).to_be_visible()
    for field, value in (
        ("name", "Test Widget"),
        ("price-cents", "1234"),
        ("stock", "5"),
        ("rating", "40"),
    ):
        page.fill(f"#product-{field}", value)
    page.click("#product-save")
    page.wait_for_url(re.compile(rf"/data/product/{SEED_PRODUCTS + 1}$"))
    heading = page.locator("#product-heading")
    expect(heading).to_have_text("Test Widget")
    page.fill("#product-name", "Test Widget 2")
    page.click("#product-save")
    expect(heading).to_have_text("Test Widget 2")
    page.click("#product-delete")
    page.click("#product-delete-confirm")
    page.wait_for_url(re.compile(r"/data$"))
    expect(label).to_have_text(f"Page 1 of 100 ({SEED_PRODUCTS} products)")


def _check_forms(page: Page) -> None:
    """Validate the sign-up form on blur and on submit, then submit it.

    Args:
        page: The ``/forms`` page.
    """
    page.fill("#forms-email", "ada@example")
    page.locator("#forms-email").blur()
    # Blur and submit apply the same check.
    expect(page.locator("#forms-error-email")).to_be_visible()
    page.fill("#forms-username", "ada")
    page.click("#forms-submit")
    # A rejected sign-up keeps what the visitor typed.
    expect(page.locator("#forms-error-age")).to_be_visible()
    expect(page.locator("#forms-username")).to_have_value("ada")
    # Reset clears the fields and the errors.
    page.click("#forms-reset")
    expect(page.locator("#forms-error-age")).to_have_count(0)
    expect(page.locator("#forms-username")).to_have_value("")
    page.fill("#forms-username", "ada")
    page.fill("#forms-email", "ada@example.com")
    page.fill("#forms-age", "36")
    page.click("#forms-terms")
    page.click("#forms-submit")
    expect(page.locator("#forms-count")).to_have_text("1 sign-ups")
    # An accepted sign-up clears the fields.
    expect(page.locator("#forms-username")).to_have_value("")


def _upload(page: Page, content: bytes, name: str = "hello.txt") -> str:
    """Upload a file and return the link to it.

    Args:
        page: The ``/upload`` page.
        content: The file's bytes.
        name: The file's name.

    Returns:
        The stored file's URL.
    """
    page.set_input_files(
        "#upload-files input[type=file]",
        files=[{"name": name, "mimeType": "text/plain", "buffer": content}],
    )
    page.click("#upload-start")
    link = page.locator("#upload-stored a").filter(has_text=name)
    expect(link).to_have_text(name)
    href = link.get_attribute("href")
    assert href is not None
    return href


@pytest.mark.parametrize("spec", SPECS)
@NEEDS_APP
@NEEDS_CHROMIUM
def test_interactions_work(tmp_path: Path, home: Path, spec: str):
    browser = Browser()
    with _running_playground(tmp_path, home, spec, "prod") as app:
        request = urllib.request.Request(
            f"{app.backend_url}/api/playground/stats", method="POST"
        )
        with pytest.raises(urllib.error.HTTPError):
            # Only GET and HEAD reach the stats route.
            urllib.request.urlopen(request, timeout=30)
        browser.start()
        try:
            first, second = browser.new_page(), browser.new_page()
            _check_events(_open(first, app, "/events"))
            page = _open(first, app, "/tasks")
            page.fill("#tasks-draft", "Ship it")
            page.click("#tasks-add")
            expect(page.locator("#tasks-progress")).to_have_text("1 of 4 done (25 %)")
            page.locator("#tasks-list button[role=checkbox]").nth(3).click()
            expect(page.locator("#tasks-progress")).to_have_text("2 of 4 done (50 %)")
            _check_data(_open(first, app, "/data"), app)
            _check_forms(_open(first, app, "/forms"))

            # Two visitors uploading one name keep their own files.
            first_url = _upload(_open(first, app, "/upload"), b"first")
            second_url = _upload(_open(second, app, "/upload"), b"second")
            assert first_url != second_url
            # A name with URL delimiters links to the whole name.
            third_url = _upload(_open(second, app, "/upload"), b"third", "a#b?.txt")
            for url, content in (
                (first_url, b"first"),
                (second_url, b"second"),
                (third_url, b"third"),
            ):
                with urllib.request.urlopen(url, timeout=30) as response:
                    assert response.read() == content

            page = _open(first, app, "/storage")
            # A value that str.isdigit() accepts and int() cannot parse.
            page.evaluate("localStorage.setItem('playground_visits', '\u00b2')")
            page = _open(first, app, "/storage")
            stored = page.locator("#storage-values")
            page.click("#storage-local")
            page.fill("#storage-cookie", "note-1")
            page.click("#storage-local")
            expect(stored).to_contain_text("note-1")
            expect(stored).to_contain_text("2")
            # The browser keeps both values across a page load.
            _open(first, app, "/storage")
            expect(stored).to_contain_text("note-1")
            expect(stored).to_contain_text("2")
            # The input shows the value the browser kept.
            expect(page.locator("#storage-cookie")).to_have_value("note-1")

            # A slider shows its state when its page mounts again.
            page = _open(first, app, "/charts")
            page.locator("#charts-resolution [role=slider]").press("End")
            expect(page.locator("#charts-points")).not_to_have_text("Points: 24")
            points = page.locator("#charts-points").inner_text().split()[-1]
            page.click("a[href='/counter']")
            page.wait_for_url(re.compile(r"/counter$"))
            page.click("a[href='/charts']")
            expect(page.locator("#charts-resolution [role=slider]")).to_have_attribute(
                "aria-valuenow", points
            )

            # Two visitors of one room see each other and each other's updates.
            a = _open(first, app, "/room/check")
            b = _open(second, app, "/room/check")
            for page in (a, b):
                expect(page.locator("#room-presence-count")).to_have_text("Here: 2")
            a.click("#room-increment")
            expect(b.locator("#room-count")).to_have_text("1")
            b.click("#room-burst")
            expect(a.locator("#room-count")).to_have_text("11")
            b.click("#room-broadcast")
            expect(a.locator("#room-last")).to_contain_text("Last broadcast: 1")
            # Entering another room leaves the first one.
            b = _open(second, app, "/room/other")
            expect(b.locator("#room-presence-count")).to_have_text("Here: 1")
            expect(a.locator("#room-presence-count")).to_have_text("Here: 1")
            b = _open(second, app, "/room/check")
            expect(a.locator("#room-presence-count")).to_have_text("Here: 2")
            b.click("#room-leave")
            expect(a.locator("#room-presence-count")).to_have_text("Here: 1")
            expect(a.locator("#room-presence")).to_have_text(
                a.locator("#room-me").inner_text()
            )
            # A second Leave, with no room linked, does nothing.
            b.click("#room-leave")
            b.click("#room-broadcast")
            expect(b.locator("#room-last")).to_contain_text("Last broadcast: 2")
            expect(b.get_by_text("An error occurred.")).to_have_count(0)
            for tab in (first, second):
                tab.raise_errors()
        finally:
            browser.close()
