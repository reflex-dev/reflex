"""Tests (b2)+(d): reflex.testing.AppHarness used twice in ONE process.

- test_sequential_harnesses: harness1 (AppOne) start/verify/stop, then harness2
  (AppTwo) in the same process -> no page/state leakage.
- test_simultaneous_harnesses: both harnesses running at the same time, driven
  concurrently in one browser -> no cross-talk (events land on the right app).

Run:
    cd <this dir>
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    REFLEX_TELEMETRY_ENABLED=false \
    <rcx-venv>/bin/python -m pytest test_appharness_multi.py -x -s -v

Chromium: /opt/pw-browsers/chromium (playwright executable_path).
"""

import time

import pytest
from playwright.sync_api import sync_playwright

from reflex.testing import AppHarness

CHROMIUM = "/opt/pw-browsers/chromium"


def AppOne():
    import reflex as rx

    class CounterState(rx.State):
        count: int = 0

        @rx.event
        def increment(self):
            self.count += 1  # AppOne increments by 1

    @rx.page(route="/one-only", title="OneOnly")
    def one_only():
        return rx.heading("ONE-ONLY-PAGE", id="marker")

    def index():
        return rx.vstack(
            rx.heading("APPONE-INDEX", id="marker"),
            rx.text(CounterState.count, id="count"),
            rx.button("inc", id="inc", on_click=CounterState.increment),
        )

    app = rx.App()
    app.add_page(index)


def AppTwo():
    import reflex as rx

    class CounterState(rx.State):
        count: int = 0

        @rx.event
        def increment(self):
            self.count += 10  # AppTwo increments by 10

    @rx.page(route="/two-only", title="TwoOnly")
    def two_only():
        return rx.heading("TWO-ONLY-PAGE", id="marker")

    def index():
        return rx.vstack(
            rx.heading("APPTWO-INDEX", id="marker"),
            rx.text(CounterState.count, id="count"),
            rx.button("inc", id="inc", on_click=CounterState.increment),
        )

    app = rx.App()
    app.add_page(index)


def _collect_console(page, sink):
    page.on("console", lambda m: sink.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: sink.append(f"[pageerror] {e}"))


def _wait_marker(page, url, expected, timeout_ms=60000):
    page.goto(url, wait_until="load", timeout=timeout_ms)
    page.wait_for_selector("#marker", timeout=timeout_ms)
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        text = page.inner_text("#marker")
        if text == expected:
            return text
        time.sleep(0.25)
    return page.inner_text("#marker")


def _click_and_expect_count(page, expected, timeout_s=15):
    page.click("#inc")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if page.inner_text("#count") == str(expected):
            return True
        time.sleep(0.2)
    return False


def _check_app(page, harness, marker, unique_route, unique_marker, other_route, delta):
    """Full functional check of one harness-served app."""
    base = harness.frontend_url.rstrip("/")
    assert _wait_marker(page, base + "/", marker) == marker
    # initial count renders 0 after hydration
    deadline = time.time() + 30
    while time.time() < deadline and page.inner_text("#count") != "0":
        time.sleep(0.25)
    assert page.inner_text("#count") == "0", f"count did not hydrate to 0: {page.inner_text('#count')!r}"
    assert _click_and_expect_count(page, delta), f"count did not reach {delta} after click"
    assert _click_and_expect_count(page, 2 * delta), f"count did not reach {2 * delta}"
    # unique page exists
    assert _wait_marker(page, base + unique_route, unique_marker) == unique_marker
    # other app's unique page must NOT be served
    page.goto(base + other_route, wait_until="load")
    time.sleep(1.5)
    content = page.content()
    assert "ONE-ONLY-PAGE" not in content if other_route == "/one-only" else "TWO-ONLY-PAGE" not in content, (
        f"LEAK: {other_route} served other app's page on {base}"
    )
    assert "404" in content, f"expected 404 page for {other_route}, got: {content[:500]}"


@pytest.fixture(scope="module")
def pw():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        yield browser
        browser.close()


def test_sequential_harnesses(tmp_path_factory, pw):
    """Two AppHarness instances with DIFFERENT app sources, one after the other."""
    console1, console2 = [], []

    with AppHarness.create(
        root=tmp_path_factory.mktemp("appone"), app_source=AppOne
    ) as harness1:
        page = pw.new_page()
        _collect_console(page, console1)
        _check_app(page, harness1, "APPONE-INDEX", "/one-only", "ONE-ONLY-PAGE", "/two-only", 1)
        page.close()

    with AppHarness.create(
        root=tmp_path_factory.mktemp("apptwo"), app_source=AppTwo
    ) as harness2:
        page = pw.new_page()
        _collect_console(page, console2)
        _check_app(page, harness2, "APPTWO-INDEX", "/two-only", "TWO-ONLY-PAGE", "/one-only", 10)
        page.close()

    print("\nconsole harness1:", *console1, sep="\n  ")
    print("\nconsole harness2:", *console2, sep="\n  ")


def test_simultaneous_harnesses(tmp_path_factory, pw):
    """Two AppHarness instances RUNNING AT THE SAME TIME in one process."""
    console1, console2 = [], []
    with AppHarness.create(
        root=tmp_path_factory.mktemp("simone"), app_source=AppOne
    ) as harness1, AppHarness.create(
        root=tmp_path_factory.mktemp("simtwo"), app_source=AppTwo
    ) as harness2:
        page1 = pw.new_page()
        page2 = pw.new_page()
        _collect_console(page1, console1)
        _collect_console(page2, console2)
        # interleave: load both, click alternately
        base1 = harness1.frontend_url.rstrip("/")
        base2 = harness2.frontend_url.rstrip("/")
        assert _wait_marker(page1, base1 + "/", "APPONE-INDEX") == "APPONE-INDEX"
        assert _wait_marker(page2, base2 + "/", "APPTWO-INDEX") == "APPTWO-INDEX"
        for pg in (page1, page2):
            deadline = time.time() + 30
            while time.time() < deadline and pg.inner_text("#count") != "0":
                time.sleep(0.25)
            assert pg.inner_text("#count") == "0"
        # alternate clicks: app1 delta=1, app2 delta=10
        assert _click_and_expect_count(page1, 1), "app1 click 1 failed"
        assert _click_and_expect_count(page2, 10), "app2 click 1 failed (cross-talk? wrong delta?)"
        assert _click_and_expect_count(page1, 2), "app1 click 2 failed"
        assert _click_and_expect_count(page2, 20), "app2 click 2 failed"
        # unique-route isolation while both alive
        assert _wait_marker(page1, base1 + "/one-only", "ONE-ONLY-PAGE") == "ONE-ONLY-PAGE"
        assert _wait_marker(page2, base2 + "/two-only", "TWO-ONLY-PAGE") == "TWO-ONLY-PAGE"
        page1.goto(base1 + "/two-only", wait_until="load")
        time.sleep(1.5)
        assert "TWO-ONLY-PAGE" not in page1.content(), "LEAK: app1 served app2's page"
        page2.goto(base2 + "/one-only", wait_until="load")
        time.sleep(1.5)
        assert "ONE-ONLY-PAGE" not in page2.content(), "LEAK: app2 served app1's page"
        page1.close()
        page2.close()

    print("\nconsole sim harness1:", *console1, sep="\n  ")
    print("\nconsole sim harness2:", *console2, sep="\n  ")
