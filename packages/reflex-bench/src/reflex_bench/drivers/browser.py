"""Drive headless Chromium through Playwright and time pages on the harness's clock.

A :class:`Browser` is one Chromium with its Playwright driver. Each
:meth:`Browser.new_page` opens a :class:`Tab` in a fresh browser context (a cold
cache) with ``bench_page.js`` installed as an init script, so it runs before any
page script in every document, reloaded ones included. The script records
*marks*: when the page itself saw a condition hold (the page emits the "done"
signal; the harness only waits for it).

Thread rules: the sync Playwright API only works on the thread that started it
(from another thread it raises ``greenlet.error: Cannot switch to a different
thread``). The scheduler runs every hook of an instance on one thread, but runs
the teardown hooks on a fresh thread after a timeout or Ctrl-C. So
:meth:`Browser.close` closes normally on the owner thread and kills from any
other, and :meth:`Browser.kill` never touches Playwright: it SIGKILLs Chromium,
found through the owner token in its environment together with the helpers it
spawned, and the Playwright driver, so a hook still blocked in the page gets an
error at once. Browsers still open when the interpreter exits are killed.

Clocks: a mark carries ``performance.now()`` (since navigation start) and
``Date.now()``. The :class:`Anchor` taken at start maps the wall clock onto
``time.perf_counter()``, on which an app's readiness and log times count
(:attr:`~reflex_bench.drivers.app_process.AppProcess.t0`).
"""

from __future__ import annotations

import atexit
import contextlib
import os
import re
import secrets
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil

from reflex_bench.drivers.app_process import OWNER_ENV, kill_owned, owned_processes

if TYPE_CHECKING:
    from playwright.sync_api import Browser as PlaywrightBrowser
    from playwright.sync_api import (
        CDPSession,
        ConsoleMessage,
        Page,
        Playwright,
        Response,
        WebSocket,
    )

    from reflex_bench.drivers.app_process import AppProcess

BENCH_JS = Path(__file__).with_name("bench_page.js").read_text(encoding="utf-8")
HYDRATED = "#bench-hydrated"
NAV_TIMEOUT_S = 120.0
_ANCHOR_READS = 3
# A socket.io event frame: "42", an optional namespace, then ["name", ...].
_SOCKETIO_EVENT = re.compile(r'42(?:/[^,]*,)?\["([^"]+)"')

Mark = dict[str, float]


@dataclass(frozen=True)
class Anchor:
    """A reading of the wall clock between two reads of ``time.perf_counter()``.

    Attributes:
        perf: The middle of the two ``perf_counter`` reads.
        epoch: ``time.time()``.
        spread: The time between the two reads: how far off the pair can be.
    """

    perf: float
    epoch: float
    spread: float

    @classmethod
    def take(cls) -> Anchor:
        """Read both clocks back to back a few times and keep the tightest pair.

        Returns:
            The anchor.
        """
        anchors = []
        for _ in range(_ANCHOR_READS):
            before = time.perf_counter()
            epoch = time.time()
            after = time.perf_counter()
            anchors.append(cls((before + after) / 2, epoch, after - before))
        return min(anchors, key=lambda anchor: anchor.spread)

    def perf_at(self, epoch: float) -> float:
        """Map a wall clock time onto ``time.perf_counter()``.

        The host's clocks are shared by the harness and the browser, so a page's
        ``Date.now()`` maps with millisecond resolution.

        Args:
            epoch: Seconds since the epoch.

        Returns:
            The ``perf_counter()`` value of that moment.
        """
        return epoch - self.epoch + self.perf


def _payload_size(payload: str | bytes) -> int:
    """Count the bytes of a websocket frame's payload.

    Args:
        payload: The payload.

    Returns:
        Its size in bytes (UTF-8 for text frames).
    """
    return len(payload.encode() if isinstance(payload, str) else payload)


class Tab:
    """A page in its own browser context, with what it reported.

    Page errors, console messages and websocket frames are collected as they
    arrive (Playwright delivers events on the owner thread during its calls).

    Attributes:
        page: The Playwright page.
        cdp: A DevTools session of the page, e.g. for ``Network.setCacheDisabled``.
        ws_bytes: Payload bytes of the page's websocket frames, both directions.
        ws_events: How often each socket.io event arrived, by name.
        page_errors: The page's uncaught errors since :meth:`raise_errors`,
            oldest first.
        last_error: The text of the last console error since
            :meth:`drain_console`, if any.
    """

    def __init__(self, page: Page, cdp: CDPSession) -> None:
        """Start collecting the page's events.

        Args:
            page: The page, with ``bench_page.js`` installed.
            cdp: A DevTools session of the page.
        """
        self.page = page
        self.cdp = cdp
        self.ws_bytes = 0
        self.ws_events: Counter[str] = Counter()
        self.page_errors: list[str] = []
        self.last_error: str | None = None
        self._console: Counter[str] = Counter()
        self._responses: list[Response] = []
        page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        page.on("console", self._on_console)
        page.on("websocket", self._on_websocket)
        page.on("response", self._on_response)

    def _on_response(self, response: Response) -> None:
        """Keep a response, for :meth:`transfer_bytes`.

        Args:
            response: The response.
        """
        self._responses.append(response)

    def _on_console(self, message: ConsoleMessage) -> None:
        """Count console errors and warnings.

        Args:
            message: The console message.
        """
        if message.type in {"error", "warning"}:
            self._console[message.type] += 1
            if message.type == "error":
                self.last_error = message.text

    def _on_websocket(self, websocket: WebSocket) -> None:
        """Count a websocket's frames.

        Args:
            websocket: The websocket the page opened.
        """
        websocket.on("framesent", self._on_frame_sent)
        websocket.on("framereceived", self._on_frame_received)

    def _on_frame_sent(self, payload: str | bytes) -> None:
        """Count a sent frame.

        Args:
            payload: The frame's payload.
        """
        self.ws_bytes += _payload_size(payload)

    def _on_frame_received(self, payload: str | bytes) -> None:
        """Count a received frame and the socket.io event it carries.

        Args:
            payload: The frame's payload.
        """
        self.ws_bytes += _payload_size(payload)
        if isinstance(payload, str) and (event := _SOCKETIO_EVENT.match(payload)):
            self.ws_events[event[1]] += 1

    def mark(self, id: str) -> Mark | None:
        """Read a mark.

        Args:
            id: The mark id.

        Returns:
            ``{"perf": ms since navigation start, "epoch": Date.now()}``, or
            ``None`` when the page did not record it (yet).
        """
        return self.page.evaluate("id => window.__bench.marks[id] ?? null", id)

    def wait_mark(self, id: str, timeout: float) -> Mark:
        """Wait for a mark, also across a navigation of the page.

        Args:
            id: The mark id.
            timeout: Seconds to wait.

        Returns:
            The mark.
        """
        return self.page.wait_for_function(
            "id => window.__bench.marks[id]", arg=id, timeout=timeout * 1000
        ).json_value()

    def poll_mark(self, id: str, timeout: float) -> Mark | None:
        """Wait a little for a mark.

        Args:
            id: The mark id.
            timeout: Seconds to wait, more than 0.

        Returns:
            The mark, or ``None`` when it did not come.
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        try:
            return self.wait_mark(id, timeout)
        except PlaywrightTimeoutError:
            return None

    def watch(self, id: str, kind: str, selector: str, expected: str | None) -> None:
        """Arm a watch: the page records mark ``id`` the first time the condition holds.

        The watch, and its mark once recorded, survive a reload of the page.

        Args:
            id: The mark id.
            kind: ``present``, ``text`` (equals), ``changed`` (text differs),
                ``style:<property>`` (computed style equals) or ``naturalWidth``.
            selector: The element.
            expected: The value to wait for (``present``: ignored).
        """
        self.page.evaluate(
            "([id, kind, selector, expected]) =>"
            " window.__bench.watch(id, kind, selector, expected)",
            [id, kind, selector, expected],
        )

    def unwatch(self, id: str) -> None:
        """Stop a watch that is no longer needed, so it does not stay pending.

        Args:
            id: The mark id.
        """
        self.page.evaluate("id => window.__bench.unwatch(id)", id)

    def read(self, kind: str, selector: str) -> str | None:
        """Read what a watch of this kind compares.

        Args:
            kind: The watch kind.
            selector: The element.

        Returns:
            The value, or ``None`` without the element (or a loaded image).
        """
        return self.page.evaluate(
            "([kind, selector]) => window.__bench.value(kind, selector)",
            [kind, selector],
        )

    def wait_value(self, kind: str, selector: str, timeout: float) -> str:
        """Wait until the page has what a watch of this kind compares, and read it.

        Args:
            kind: The watch kind.
            selector: The element.
            timeout: Seconds to wait.

        Returns:
            The value.
        """
        return self.page.wait_for_function(
            "([kind, selector]) => { const value = window.__bench.value(kind, selector);"
            " return value === null ? null : { value }; }",
            arg=[kind, selector],
            timeout=timeout * 1000,
        ).json_value()["value"]

    def pending(self) -> list[str]:
        """List the watches still waiting.

        Returns:
            Their mark ids.
        """
        return self.page.evaluate("() => window.__bench.pending()")

    def set_alive(self) -> str:
        """Tag the current document; a full reload replaces it and loses the tag.

        Returns:
            The tag.
        """
        token = uuid.uuid4().hex
        self.page.evaluate("token => { window.__BENCH_ALIVE = token; }", token)
        return token

    def alive(self) -> str | None:
        """Read the current document's tag.

        Returns:
            The tag :meth:`set_alive` set, or ``None`` in a new document.
        """
        return self.page.evaluate("() => window.__BENCH_ALIVE ?? null")

    def wait_quiet(self, seconds: float, timeout: float) -> None:
        """Wait until no watch is pending and the DOM did not change for a while.

        Args:
            seconds: How long the DOM must not have changed.
            timeout: Seconds to wait.
        """
        self.page.wait_for_function(
            "ms => window.__bench.quiet(ms) && !window.__bench.pending().length",
            arg=seconds * 1000,
            timeout=timeout * 1000,
        )

    def click(self, selector: str) -> bool:
        """Click an element from the page's script, without Playwright's actionability waits.

        Args:
            selector: The element.

        Returns:
            Whether the element was there.
        """
        return self.page.evaluate(
            "selector => { const el = document.querySelector(selector);"
            " el?.click(); return el !== null; }",
            selector,
        )

    def reload(self) -> None:
        """Reload the page and return once it has loaded, stylesheets and images included."""
        self.page.reload(wait_until="load", timeout=NAV_TIMEOUT_S * 1000)

    def settle(self, seconds: float) -> None:
        """Let the page run for a while, delivering its events.

        Args:
            seconds: How long.
        """
        self.page.wait_for_timeout(seconds * 1000)

    def timings(self) -> dict[str, Any]:
        """Read the page's paint and long task timings.

        Returns:
            ``fcp`` and ``lcp`` (ms since navigation start, ``None`` when not
            observed), ``longtasks`` and ``loafs`` (``{"start", "duration"}`` in
            ms) and ``time_origin`` (``performance.timeOrigin``).
        """
        return self.page.evaluate(
            "() => { const b = window.__bench; return {"
            " fcp: b.paints['first-contentful-paint'] ?? null, lcp: b.lcp,"
            " longtasks: b.longtasks, loafs: b.loafs, time_origin: b.timeOrigin }; }"
        )

    def transfer_bytes(self) -> int:
        """Sum the encoded body sizes of every HTTP response of the page.

        Returns:
            Bytes received, as they came over the wire (compressed when served so).
        """
        return sum(
            response.request.sizes()["responseBodySize"]
            for response in self._responses
            if response.status != 101
        )

    def raise_errors(self) -> None:
        """Fail on uncaught page errors since the last call.

        Raises:
            RuntimeError: With the errors' messages.
        """
        if self.page_errors:
            errors, self.page_errors = self.page_errors, []
            msg = f"the page raised {len(errors)} error(s): {'; '.join(errors)}"
            raise RuntimeError(msg)

    def drain_console(self) -> dict[str, int]:
        """Take the console error and warning counts since the last call, and forget the last error.

        Returns:
            Messages per type (``error``, ``warning``).
        """
        counts, self._console = dict(self._console), Counter()
        self.last_error = None
        return counts

    def close(self) -> None:
        """Close the page's browser context."""
        self.page.context.close()


@dataclass(frozen=True)
class Interactive:
    """When a page was hydrated (tier 3), on the harness's and the page's clocks.

    Attributes:
        tab: The open page.
        interactive_ready: Seconds since the app's t0 when the page showed
            ``#bench-hydrated``: the websocket connected and the first state
            update applied.
        nav_to_interactive_s: The same moment in seconds since navigation start,
            the page's own number.
        fcp_s: First contentful paint, in seconds since the app's t0.
        lcp_s: The largest contentful paint so far, in seconds since the app's
            t0, when observed.
        navigation_start: Navigation start, in seconds since the epoch.
    """

    tab: Tab
    interactive_ready: float
    nav_to_interactive_s: float
    fcp_s: float
    lcp_s: float | None
    navigation_start: float


_LIVE: set[Browser] = set()
_LIVE_LOCK = threading.Lock()


def _hydration_mark(tab: Tab) -> Mark:
    """Read the mark the page recorded when ``#bench-hydrated`` appeared.

    Args:
        tab: The page, showing ``#bench-hydrated``.

    Returns:
        The mark.

    Raises:
        RuntimeError: When the page recorded none (no ``bench_page.js``).
    """
    mark = tab.mark("hydrated")
    if mark is None:
        msg = f"the page did not record {HYDRATED} (no bench_page.js?)"
        raise RuntimeError(msg)
    return mark


def _driver_of(token: str) -> psutil.Process | None:
    """Find the Playwright driver of a browser: the parent of its owned root.

    Playwright starts its driver with the harness's environment, so the driver
    does not carry the owner token; it is the harness's child that started the
    browser.

    Args:
        token: The browser's owner token.

    Returns:
        The driver, or ``None`` when it cannot be told.
    """
    owned = owned_processes(token)
    pids = {proc.pid for proc in owned}
    me = os.getpid()
    for proc in owned:
        with contextlib.suppress(psutil.Error):
            parent = proc.parent()
            if parent is not None and parent.pid not in pids and parent.ppid() == me:
                return parent
    return None


class Browser:
    """A headless Chromium, used from the thread that started it.

    Attributes:
        headless: Whether Chromium runs headless (the headless shell).
        cpu_throttle: The CPU slowdown applied to every page (1: none).
        token: The owner token in Chromium's environment.
        anchor: The clock anchor, taken at :meth:`start`.
    """

    def __init__(self, *, headless: bool = True, cpu_throttle: int = 1) -> None:
        """Plan the browser; nothing starts yet.

        Args:
            headless: Whether to run headless.
            cpu_throttle: Slow every page's CPU down this many times, through the
                DevTools ``Emulation.setCPUThrottlingRate``.
        """
        self.headless = headless
        self.cpu_throttle = cpu_throttle
        self.token = secrets.token_hex(8)
        self.anchor: Anchor | None = None
        self._owner: threading.Thread | None = None
        self._playwright: Playwright | None = None
        self._browser: PlaywrightBrowser | None = None
        self._driver: psutil.Process | None = None
        self._closed = False

    @property
    def closed(self) -> bool:
        """Whether the browser was closed or killed.

        Returns:
            True once it was.
        """
        return self._closed

    def start(self) -> None:
        """Start Playwright and Chromium; the calling thread owns the browser.

        Raises:
            RuntimeError: When the browser was already started or closed.
        """
        # Imported here: `reflex-bench list` imports every suite, and Playwright
        # alone adds about 0.1 s to it.
        from playwright.sync_api import sync_playwright

        if self._owner is not None or self._closed:
            msg = "a Browser starts once"
            raise RuntimeError(msg)
        self._owner = threading.current_thread()
        with _LIVE_LOCK:
            _LIVE.add(self)
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless, env={**os.environ, OWNER_ENV: self.token}
        )
        self._driver = _driver_of(self.token)
        self.anchor = Anchor.take()
        if self._closed:
            # Another thread killed the browser while this one started it.
            self.kill()
            msg = "the browser was killed while it started"
            raise RuntimeError(msg)

    def owns_thread(self) -> bool:
        """Tell whether the calling thread may use the browser.

        Returns:
            Whether the browser is open and was started by this thread.
        """
        return not self._closed and threading.current_thread() is self._owner

    def new_page(self) -> Tab:
        """Open a page in a fresh browser context.

        Returns:
            The page, with ``bench_page.js`` installed and the CPU throttled.

        Raises:
            RuntimeError: When the browser is closed or not started, or the
                calling thread does not own it.
        """
        if self._closed or self._browser is None:
            msg = (
                "the browser is closed" if self._closed else "start() the browser first"
            )
            raise RuntimeError(msg)
        if not self.owns_thread():
            owner = self._owner.name if self._owner else "?"
            msg = f"the browser belongs to thread {owner!r}; Playwright refuses other threads"
            raise RuntimeError(msg)
        context = self._browser.new_context()
        context.add_init_script(BENCH_JS)
        page = context.new_page()
        cdp = context.new_cdp_session(page)
        if self.cpu_throttle > 1:
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": self.cpu_throttle})
        return Tab(page, cdp)

    def interactive(self, app: AppProcess, path: str = "/") -> Interactive:
        """Open a fresh page of a started app and wait until it is hydrated (tier 3).

        Also fills ``app.readiness.interactive_ready``.

        Args:
            app: The app, HTTP-ready.
            path: The page's path.

        Returns:
            Tier 3 on both clocks, the paint times and the open page.

        Raises:
            RuntimeError: When the page did not record the hydration mark.
        """
        anchor = self.anchor
        tab = self.new_page()
        assert anchor is not None  # taken by start(), which new_page() needs
        timeout = NAV_TIMEOUT_S * 1000
        try:
            tab.page.goto(
                (app.frontend_url or app.backend_url) + path,
                wait_until="commit",
                timeout=timeout,
            )
            tab.page.wait_for_selector(HYDRATED, state="attached", timeout=timeout)
            mark = _hydration_mark(tab)
            fcp = tab.page.wait_for_function(
                "() => window.__bench.paints['first-contentful-paint']", timeout=timeout
            ).json_value()
            lcp = tab.timings()["lcp"]
        except BaseException:
            # The browser may be gone (killed from another thread): keep the
            # original error.
            with contextlib.suppress(Exception):
                tab.close()
            raise
        navigation_start = (mark["epoch"] - mark["perf"]) / 1000

        def since_t0(ms: float) -> float:
            return anchor.perf_at(navigation_start + ms / 1000) - app.t0

        interactive_ready = since_t0(mark["perf"])
        if app.readiness is not None:
            app.readiness.interactive_ready = interactive_ready
        return Interactive(
            tab=tab,
            interactive_ready=interactive_ready,
            nav_to_interactive_s=mark["perf"] / 1000,
            fcp_s=since_t0(fcp),
            lcp_s=None if lcp is None else since_t0(lcp),
            navigation_start=navigation_start,
        )

    def close_tab(self, tab: Tab) -> None:
        """Close a page, or kill the browser from a thread that does not own it.

        Args:
            tab: The page.
        """
        if self.owns_thread():
            tab.close()
        else:
            self.kill()

    def close(self) -> None:
        """Close Chromium and stop Playwright; from another thread, :meth:`kill`.

        Whatever the normal close leaves is killed.
        """
        if self._closed:
            return
        if threading.current_thread() is not self._owner:
            self.kill()
            return
        try:
            if self._browser is not None:
                self._browser.close()
            if self._playwright is not None:
                self._playwright.stop()
        finally:
            self.kill()

    def kill(self) -> None:
        """SIGKILL Chromium and the Playwright driver, from any thread; idempotent.

        Chromium is found through the owner token in its environment, with the
        helpers it spawned, and the driver by the pid found at :meth:`start`.
        Nothing here touches Playwright.
        """
        self._closed = True
        with _LIVE_LOCK:
            _LIVE.discard(self)
        kill_owned(self.token, () if self._driver is None else (self._driver,))


def _kill_live_browsers() -> None:
    """Kill the browsers still open when the harness exits, e.g. after Ctrl-C."""
    with _LIVE_LOCK:
        browsers = list(_LIVE)
    for browser in browsers:
        # One failure must not keep the other browsers alive.
        with contextlib.suppress(Exception):
            browser.kill()


atexit.register(_kill_live_browsers)
