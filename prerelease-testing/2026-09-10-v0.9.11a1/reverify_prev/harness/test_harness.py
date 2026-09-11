"""FINDING-016 re-verification: does reflex[testing] + AppHarness run an app end to end?

Runs BOTH the dev harness (AppHarness) and the prod harness (AppHarnessProd) in one
pytest session, and drives each in real Chromium via Playwright.

    <venv>/bin/python -m pytest test_harness.py -x -s
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import sync_playwright

import reflex
from reflex.testing import AppHarness, AppHarnessProd

assert "site-packages" in reflex.__file__ and "/envs/" in reflex.__file__, reflex.__file__


def CounterApp():
    import reflex as rx

    class CounterState(rx.State):
        count: int = 0

        @rx.event
        def inc(self):
            self.count += 1

    def index() -> rx.Component:
        return rx.vstack(
            rx.heading("HARNESS", id="hd"),
            rx.text(CounterState.count.to_string(), id="count"),
            rx.button("inc", on_click=CounterState.inc, id="btn"),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def dev_harness(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
        root=tmp_path_factory.mktemp("hdev"), app_source=CounterApp
    ) as harness:
        yield harness


@pytest.fixture(scope="module")
def prod_harness(tmp_path_factory) -> Generator[AppHarnessProd, None, None]:
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("hprod"), app_source=CounterApp
    ) as harness:
        yield harness


def _drive(url: str, shot: str) -> tuple[str, str, list[str]]:
    console: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_context().new_page()
        page.on("console", lambda m: console.append(f"{m.type}:{m.text}"))
        page.on("pageerror", lambda e: console.append(f"pageerror:{e}"))
        page.goto(url, wait_until="load", timeout=90000)
        page.wait_for_selector("#count", timeout=60000)
        page.wait_for_function(
            "document.querySelector('#count').innerText === '0'", timeout=30000
        )
        before = page.inner_text("#count")
        page.click("#btn")
        page.wait_for_function(
            "document.querySelector('#count').innerText === '1'", timeout=30000
        )
        after = page.inner_text("#count")
        page.screenshot(path=shot)
        browser.close()
    return before, after, console


def test_import_testing_bare():
    """reflex.testing must import (0.9.10.post2 raised ModuleNotFoundError: uvicorn)."""
    import reflex.testing  # noqa: F401


def test_dev_harness_end_to_end(dev_harness: AppHarness):
    assert dev_harness.frontend_url is not None
    before, after, console = _drive(dev_harness.frontend_url, "/tmp/harness_dev.png")
    print("DEV url:", dev_harness.frontend_url, "before:", before, "after:", after)
    print("DEV console:", console)
    assert (before, after) == ("0", "1")


def test_prod_harness_end_to_end(prod_harness: AppHarnessProd):
    assert prod_harness.frontend_url is not None
    before, after, console = _drive(prod_harness.frontend_url, "/tmp/harness_prod.png")
    print("PROD url:", prod_harness.frontend_url, "before:", before, "after:", after)
    print("PROD console:", console)
    assert (before, after) == ("0", "1")
