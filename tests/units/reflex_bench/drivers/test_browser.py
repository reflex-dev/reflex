"""Tests for reflex_bench.drivers.browser.

The page tests load a static stand-in for a Reflex page
(``fixtures/html/bench_page.html``) from a local HTTP server into a real headless
Chromium. They skip where no Playwright chromium is installed and never install
one. As in the scheduler, the browser belongs to one worker thread.
"""

from __future__ import annotations

import functools
import http.server
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeVar

import psutil
import pytest
from reflex_bench import machine
from reflex_bench.drivers import browser as browser_module
from reflex_bench.drivers.app_process import Readiness, owned_processes
from reflex_bench.drivers.browser import Anchor, Browser
from reflex_bench.scheduler import ABANDON_GRACE_S

HTML = Path(__file__).parents[1] / "fixtures" / "html"
needs_chromium = pytest.mark.skipif(
    not machine._playwright_chromium(),
    reason="no Playwright chromium (uv run playwright install --only-shell chromium)",
)
_T = TypeVar("_T")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the fixture pages without logging every request."""

    def log_message(self, format: str, *args: Any) -> None:
        """Drop the request log line.

        Args:
            format: The message format.
            *args: Its arguments.
        """


@pytest.fixture(scope="module")
def site() -> Iterator[str]:
    """Serve ``fixtures/html`` on a free local port.

    Yields:
        The server's base URL.
    """
    handler = functools.partial(_QuietHandler, directory=str(HTML))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()


@pytest.fixture
def owner() -> Iterator[ThreadPoolExecutor]:
    """Run jobs on one thread, like a benchmark instance's worker thread.

    Yields:
        The executor.
    """
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="owner") as pool:
        yield pool


def on(owner: ThreadPoolExecutor, fn: Callable[..., _T], *args: Any) -> _T:
    """Run a function on the owner thread and wait for it.

    Args:
        owner: The owner thread.
        fn: The function.
        *args: Its arguments.

    Returns:
        What it returned.
    """
    return owner.submit(fn, *args).result(timeout=60)


@pytest.fixture
def browser(owner: ThreadPoolExecutor) -> Iterator[Browser]:
    """Start a browser on the owner thread and close it after the test.

    Yields:
        The browser.
    """
    browser = Browser()
    on(owner, browser.start)
    yield browser
    on(owner, browser.close)
    assert owned_processes(browser.token) == []


def test_playwright_is_imported_lazily():
    # `reflex-bench list` imports every suite; Playwright alone takes ~0.1 s.
    code = (
        "import sys, reflex_bench.drivers.browser;"
        "assert not [m for m in sys.modules if m.startswith('playwright')]"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_anchor_maps_the_wall_clock_to_perf_counter():
    anchor = Anchor.take()
    assert 0 <= anchor.spread < 0.01
    epoch, perf = time.time(), time.perf_counter()
    assert anchor.perf_at(epoch) == pytest.approx(perf, abs=0.01)


def test_the_page_script_is_one_file_next_to_the_driver():
    script = Path(browser_module.__file__).with_name("bench_page.js")
    assert script.read_text(encoding="utf-8") == browser_module.BENCH_JS


@needs_chromium
def test_marks_carry_both_clocks_and_map_onto_the_harness_clock(
    owner: ThreadPoolExecutor, browser: Browser, site: str
):
    def load() -> tuple[list[float], dict[str, float], dict[str, Any], float]:
        tab = browser.new_page()
        started = time.perf_counter()
        tab.page.goto(f"{site}/bench_page.html", wait_until="commit")
        tab.page.wait_for_selector("#bench-hydrated", state="attached")
        seen = time.perf_counter()
        mark = tab.mark("hydrated")
        assert mark is not None
        before = time.perf_counter()
        now = tab.page.evaluate("Date.now()")
        after = time.perf_counter()
        return [started, seen, before, after], mark, tab.timings(), now

    (started, seen, before, after), mark, timings, now = on(owner, load)
    # performance.now() since navigation start and Date.now() of one moment.
    assert mark["perf"] >= 100
    assert timings["time_origin"] + mark["perf"] == pytest.approx(mark["epoch"], abs=5)
    assert browser.anchor is not None
    # Date.now() has millisecond resolution.
    assert (
        started - 0.002 <= browser.anchor.perf_at(mark["epoch"] / 1000) <= seen + 0.002
    )
    # A Date.now() read in the page maps within 50 ms of the harness's own
    # perf_counter() readings around it.
    assert browser.anchor.perf_at(now / 1000) == pytest.approx(
        (before + after) / 2, abs=0.05
    )
    assert after - before < 0.05
    assert 0 < timings["fcp"] < mark["perf"]
    assert timings["lcp"] is not None
    assert timings["longtasks"] == []


@needs_chromium
def test_watches_see_text_attributes_and_computed_style(
    owner: ThreadPoolExecutor, browser: Browser, site: str
):
    def watch() -> tuple[dict[str, float], dict[str, float], str | None]:
        tab = browser.new_page()
        tab.page.goto(f"{site}/bench_page.html", wait_until="commit")
        tab.watch("leaf", "text", "#bench-marker-leaf", "m-updated-leaf")
        tab.watch("style", "style:font-size", ".bench-hooks", "13px")
        leaf, style = tab.wait_mark("leaf", 10), tab.wait_mark("style", 10)
        return leaf, style, tab.read("style:font-size", ".bench-hooks")

    leaf, style, font_size = on(owner, watch)
    # The style changes 100 ms after the text through an inline style attribute,
    # which no watch observes: the animation frame poll caught it.
    assert style["perf"] - leaf["perf"] == pytest.approx(100, abs=40)
    assert font_size == "13px"


@needs_chromium
def test_rearming_clears_the_mark_and_unwatch_ends_a_watch(
    owner: ThreadPoolExecutor, browser: Browser, site: str
):
    def rearm() -> dict[str, Any]:
        tab = browser.new_page()
        tab.page.goto(f"{site}/bench_page.html", wait_until="commit")
        tab.watch("leaf", "text", "#bench-marker-leaf", "m-updated-leaf")
        first = tab.wait_mark("leaf", 10)
        # A new watch under the same id must not find the old mark.
        tab.watch("leaf", "text", "#bench-marker-leaf", "m-never")
        found = {"first": first, "stale": tab.mark("leaf"), "armed": tab.pending()}
        tab.unwatch("leaf")
        found["unwatched"] = tab.pending()
        tab.wait_quiet(0.3, 10)  # nothing pending holds it up
        found["width"] = tab.wait_value("naturalWidth", 'img[alt="logo"]', 10)
        found["missing"] = tab.read("text", "#missing")
        return found

    found = on(owner, rearm)
    assert found["first"]["perf"] > 0
    assert found["stale"] is None
    assert found["armed"] == ["leaf"]
    assert found["unwatched"] == []
    assert found["width"] == "40"
    assert found["missing"] is None


@needs_chromium
def test_changed_watch_and_click(
    owner: ThreadPoolExecutor, browser: Browser, site: str
):
    def click() -> tuple[bool, dict[str, float], bool]:
        tab = browser.new_page()
        tab.page.goto(f"{site}/bench_page.html", wait_until="commit")
        before = tab.read("text", "#bench-handler")
        tab.watch("clicked", "changed", "#bench-handler", before)
        assert tab.poll_mark("clicked", 0.3) is None
        clicked = tab.click("#bench-handler")
        return clicked, tab.wait_mark("clicked", 5), tab.click("#missing")

    clicked, mark, missing = on(owner, click)
    assert clicked
    assert mark["perf"] > 0
    assert not missing


@needs_chromium
def test_a_reload_keeps_watches_and_marks_but_not_the_alive_token(
    owner: ThreadPoolExecutor, browser: Browser, site: str
):
    def reload() -> dict[str, Any]:
        tab = browser.new_page()
        tab.page.goto(f"{site}/bench_page.html?reload", wait_until="commit")
        tab.page.wait_for_selector("#bench-hydrated", state="attached")
        found: dict[str, Any] = {"token": tab.set_alive()}
        tab.watch("update", "text", "#bench-marker-leaf", "m-updated-leaf")
        # Only the reloaded document shows this marker: the watch is re-armed there.
        tab.watch("reloaded", "text", "#bench-marker-leaf", "m-reloaded-leaf")
        found["update"] = tab.wait_mark("update", 10)
        found["after_update"] = tab.alive()
        tab.wait_mark("reloaded", 10)
        found["after_reload"] = tab.alive()
        found["pending"] = tab.pending()
        # The reloaded document still reports the mark the first one recorded.
        found["kept"] = tab.mark("update")
        # Arming the id again forgets its mark in later documents too.
        tab.watch("update", "text", "#bench-marker-leaf", "m-never")
        tab.reload()
        found["rearmed"] = tab.mark("update"), tab.pending()
        return found

    found = on(owner, reload)
    assert found["after_update"] == found["token"]
    assert found["after_reload"] is None
    assert found["pending"] == []
    assert found["kept"] == found["update"]
    assert found["rearmed"] == (None, ["update"])


@needs_chromium
def test_quiet_waits_for_the_last_dom_change(
    owner: ThreadPoolExecutor, browser: Browser, site: str
):
    def quiet() -> tuple[dict[str, float], float]:
        tab = browser.new_page()
        tab.page.goto(f"{site}/bench_page.html", wait_until="commit")
        tab.wait_quiet(0.3, 10)
        return tab.wait_mark("hydrated", 1), tab.page.evaluate("performance.now()")

    hydrated, now = on(owner, quiet)
    # The last change (the style, at 300 ms) is 200 ms after hydration.
    assert now - hydrated["perf"] >= 200 + 300 - 40


@needs_chromium
def test_page_errors_fail_and_console_messages_count(
    owner: ThreadPoolExecutor, browser: Browser, site: str
):
    def load() -> tuple[list[str], dict[str, int], str | None, str | None]:
        tab = browser.new_page()
        tab.page.goto(f"{site}/bench_page.html?throw", wait_until="commit")
        tab.page.evaluate("() => { console.error('bad'); console.warn('odd'); }")
        tab.wait_mark("hydrated", 5)
        page_errors = list(tab.page_errors)
        with pytest.raises(RuntimeError, match="failed on purpose"):
            tab.raise_errors()
        tab.raise_errors()  # reported once
        assert tab.page_errors == []
        last_error = tab.last_error
        return page_errors, tab.drain_console(), last_error, tab.last_error

    page_errors, console, last_error, drained = on(owner, load)
    assert page_errors == ["bench page failed on purpose"]
    assert console == {"error": 1, "warning": 1}
    assert last_error == "bad"
    assert drained is None


@needs_chromium
def test_each_page_gets_a_fresh_context(owner: ThreadPoolExecutor, browser: Browser):
    first, second = on(owner, browser.new_page), on(owner, browser.new_page)
    assert first.page.context is not second.page.context


@needs_chromium
def test_interactive_fills_tier_3(
    owner: ThreadPoolExecutor, browser: Browser, site: str
):
    class App:
        frontend_url = site
        backend_url = site
        readiness = Readiness(spawned=0.0, ready_line=0.0, process_ready=0.01)

        def __init__(self) -> None:
            self.t0 = time.perf_counter()
            self.readiness.http_ready = 0.02

    app = App()
    result = on(owner, browser.interactive, app, "/bench_page.html")
    assert app.readiness.interactive_ready == result.interactive_ready
    elapsed = time.perf_counter() - app.t0
    assert 0.1 <= result.interactive_ready < elapsed
    assert result.nav_to_interactive_s >= 0.1
    assert 0 < result.fcp_s < result.interactive_ready
    # Navigation started after the app's t0 and before the page was interactive.
    assert browser.anchor is not None
    navigation_start = browser.anchor.perf_at(result.navigation_start)
    assert app.t0 < navigation_start < app.t0 + result.interactive_ready


@needs_chromium
def test_close_on_the_owner_thread_leaves_nothing(owner: ThreadPoolExecutor):
    browser = Browser()
    on(owner, browser.start)
    assert owned_processes(browser.token)
    on(owner, browser.close)
    assert browser.closed
    assert owned_processes(browser.token) == []
    on(owner, browser.close)  # idempotent


@needs_chromium
def test_close_from_another_thread_kills_and_ends_a_blocked_wait(
    owner: ThreadPoolExecutor, site: str, monkeypatch: pytest.MonkeyPatch
):
    browser = Browser()
    on(owner, browser.start)
    driver = browser._driver
    assert driver is not None
    assert driver.ppid() == os.getpid()
    blocked = threading.Event()

    def wait_forever() -> None:
        tab = browser.new_page()
        tab.page.goto(f"{site}/bench_page.html")
        blocked.set()
        tab.page.wait_for_selector("#never", timeout=60_000)

    # An abandoned hook: the owner thread waits in the page when the teardown
    # runs on another thread.
    waiting = owner.submit(wait_forever)
    assert blocked.wait(30)
    kills: list[str] = []
    kill = browser.kill

    def spy() -> None:
        kills.append(threading.current_thread().name)
        kill()

    monkeypatch.setattr(browser, "kill", spy)
    started = time.monotonic()
    browser.close()
    # TargetClosedError or "Connection closed", whichever process died first.
    with pytest.raises(Exception, match="closed"):
        waiting.result(timeout=ABANDON_GRACE_S)
    assert time.monotonic() - started < ABANDON_GRACE_S
    assert kills == [threading.current_thread().name]
    assert browser.closed
    assert owned_processes(browser.token) == []
    assert not driver.is_running() or driver.status() == psutil.STATUS_ZOMBIE
    browser.kill()  # idempotent
    with pytest.raises(RuntimeError, match="closed"):
        on(owner, browser.new_page)


@needs_chromium
def test_new_page_refuses_other_threads(owner: ThreadPoolExecutor, browser: Browser):
    with pytest.raises(RuntimeError, match="thread"):
        browser.new_page()
    assert not browser.owns_thread()
    assert on(owner, browser.owns_thread)


@needs_chromium
def test_kill_never_signals_pid_1_or_below(
    owner: ThreadPoolExecutor, monkeypatch: pytest.MonkeyPatch
):
    browser = Browser()
    on(owner, browser.start)
    real_kill, real_killpg = os.kill, os.killpg
    sent: list[tuple[int, int]] = []

    def kill(pid: int, sig: int) -> None:
        sent.append((pid, sig))
        if pid > 1:
            real_kill(pid, sig)

    def killpg(pgid: int, sig: int) -> None:
        sent.append((pgid, sig))
        if pgid > 1:
            real_killpg(pgid, sig)

    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(os, "killpg", killpg)
    browser.kill()
    assert signal.SIGKILL in {sig for _, sig in sent}
    assert min(pid for pid, _ in sent) > 1
    assert owned_processes(browser.token) == []


@needs_chromium
def test_exit_kills_browsers_still_open(owner: ThreadPoolExecutor):
    browser = Browser()
    on(owner, browser.start)
    browser_module._kill_live_browsers()
    assert browser.closed
    assert owned_processes(browser.token) == []
