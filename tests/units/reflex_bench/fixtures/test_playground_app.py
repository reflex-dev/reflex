"""Load every playground route in headless Chromium and fail on any page or console error.

It starts the playground for real (bun, node and network needed), in dev and in
prod mode, so it only runs when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/fixtures/test_playground_app.py``. With
``REFLEX_BENCH_NETWORK_TESTS=1`` as well, it also runs against reflex 0.8.23
from PyPI, on Python 3.12.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

import pytest
from reflex_bench import machine, subjects
from reflex_bench.context import Subject, subject_env, workspace_subject
from reflex_bench.drivers.app_process import AppProcess, cache_env
from reflex_bench.drivers.browser import HYDRATED, Browser
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


@pytest.mark.skipif(
    not APP_TESTS, reason="starts the real playground; set REFLEX_BENCH_APP_TESTS=1"
)
@pytest.mark.skipif(not machine._playwright_chromium(), reason="no Playwright chromium")
@pytest.mark.parametrize("mode", ["dev", "prod"])
@pytest.mark.parametrize("spec", SPECS)
def test_every_route_loads_without_errors(
    tmp_path: Path, home: Path, spec: str, mode: str
):
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
    browser = Browser()
    problems: list[str] = []
    try:
        app.start()
        app.wait_http_ready(timeout=300)
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
                    messages.append(message.text) if message.type == "error" else None
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
        app.stop()
    assert not problems, "\n".join(problems)
