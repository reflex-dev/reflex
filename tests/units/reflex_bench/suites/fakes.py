"""Duck-typed stand-ins for AppProcess and Browser, for driving suite hooks without reflex or Chromium.

The suites import ``AppProcess`` and ``Browser`` as module attributes, so a test
swaps them with ``monkeypatch.setattr(suite, "AppProcess", FakeApp)``.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from reflex_bench.drivers.app_process import Readiness
from reflex_bench.drivers.browser import Anchor, Interactive

Mark = dict[str, Any]


class FakeApp:
    """Records what a suite does with its app; its log is written by the fake page."""

    created: list[FakeApp] = []

    def __init__(
        self,
        python: Path,
        app_dir: Path,
        *,
        mode: str,
        reflex_version: str | None,
        env: dict[str, str],
        phases: bool = False,
    ) -> None:
        """Remember the arguments.

        Args:
            python: The subject's interpreter.
            app_dir: The app directory.
            mode: The run mode.
            reflex_version: The subject's reflex version.
            env: The environment.
            phases: Whether to log at debug level.
        """
        self.app_dir = app_dir
        self.mode = mode
        self.env = env
        self.phases = phases
        self.calls: list[str] = []
        self.readiness: Readiness | None = None
        self.frontend_url = "http://localhost:3000"
        self.backend_url = "http://localhost:8000"
        self.pid = 4242
        self.t0 = time.perf_counter()
        self.lines: list[tuple[float, str]] = []
        FakeApp.created.append(self)

    def start(self) -> Readiness:
        """Pretend the app printed its ready lines.

        Returns:
            Tier 1.
        """
        self.calls.append("start")
        self.readiness = Readiness(spawned=0.001, ready_line=1.0, process_ready=1.5)
        return self.readiness

    def wait_http_ready(self) -> float:
        """Pretend the app answered HTTP.

        Returns:
            Tier 2.
        """
        assert self.readiness is not None
        self.calls.append("http")
        self.readiness.http_ready = 2.0
        return 2.0

    def log(self, line: str, delay: float = 0.0) -> None:
        """Print a line now (plus ``delay``).

        Args:
            line: The line.
            delay: Seconds after now.
        """
        self.lines.append((time.perf_counter() - self.t0 + delay, line))

    def log_lines(self) -> list[tuple[float, str]]:
        """Copy the log.

        Returns:
            The lines with their times since t0.
        """
        return list(self.lines)

    def stop(self) -> None:
        """Record the stop."""
        self.calls.append("stop")


class FakeTab:
    """A page that shows every watched value right away, after an optional reload.

    Attributes:
        reloads: How many of the next edits reload the page instead of updating it.
        misses: How many polls find no mark before one does.
        page_errors: The uncaught errors the page reports.
        last_error: The last console error the page reports.
    """

    def __init__(self, app: FakeApp, values: dict[str, str]) -> None:
        """Create the page.

        Args:
            app: The app whose log the page writes, as the backend would.
            values: The value each selector shows before any edit.
        """
        self.app = app
        self.values = dict(values)
        self.calls: list[tuple[Any, ...]] = []
        self.watches: dict[str, tuple[str, str, str | None]] = {}
        self.token: str | None = None
        self.reloads = 0
        self.misses = 0
        self.page_errors: list[str] = []
        self.last_error: str | None = None
        self.fail: Exception | None = None
        self.closed = False
        self.cdp = FakeCdp(self.calls)
        self.ws_events: Counter[str] = Counter()

    def set_alive(self) -> str:
        """Set a new document token.

        Returns:
            The token.
        """
        self.token = uuid.uuid4().hex
        self.calls.append(("set_alive",))
        return self.token

    def alive(self) -> str | None:
        """Read the document token.

        Returns:
            The token, ``None`` after a reload.
        """
        self.calls.append(("alive",))
        return self.token

    def read(self, kind: str, selector: str) -> str | None:
        """Read what a watch compares.

        Args:
            kind: The watch kind.
            selector: The element.

        Returns:
            The value.
        """
        return self.values[selector]

    def wait_value(self, kind: str, selector: str, timeout: float) -> str:
        """Read what a watch compares.

        Args:
            kind: The watch kind.
            selector: The element.
            timeout: Seconds to wait.

        Returns:
            The value.
        """
        return self.values[selector]

    def unwatch(self, id: str) -> None:
        """Record that a watch was stopped.

        Args:
            id: The mark id.
        """
        self.calls.append(("unwatch", id))
        self.watches.pop(id, None)

    def watch(self, id: str, kind: str, selector: str, expected: str | None) -> None:
        """Arm a watch.

        Args:
            id: The mark id.
            kind: The watch kind.
            selector: The element.
            expected: The value to wait for.
        """
        self.calls.append(("watch", id, kind, selector, expected))
        self.watches[id] = (kind, selector, expected)

    def _show(self, id: str) -> Mark:
        """Apply what a watch waits for, as the backend and the page would.

        Args:
            id: The mark id.

        Returns:
            The mark.

        Raises:
            Exception: The failure the test asked for.
        """
        if self.fail is not None:
            raise self.fail
        kind, selector, expected = self.watches.pop(id)
        if id == "edit":
            self.app.log("Changes detected, reloading workers..")
            self.app.log("[timing] Compile pages: 0.10s", 0.001)
            if self.reloads:
                self.reloads -= 1
                self.token = None
        if kind != "changed" and expected is not None:
            self.values[selector] = expected
        return {"perf": 1000.0, "epoch": time.time() * 1000 + 2, "alive": self.token}

    def poll_mark(self, id: str, timeout: float) -> Mark | None:
        """Wait a little for a mark.

        Args:
            id: The mark id.
            timeout: Seconds to wait.

        Returns:
            The mark, or ``None`` while the test wants misses.
        """
        self.calls.append(("poll_mark", id))
        if self.misses:
            self.misses -= 1
            return None
        return self._show(id)

    def wait_quiet(self, seconds: float, timeout: float) -> None:
        """Record the quiet wait.

        Args:
            seconds: The quiet period.
            timeout: Seconds to wait.
        """
        self.calls.append(("wait_quiet", seconds))

    def click(self, selector: str) -> bool:
        """Record a click.

        Args:
            selector: The element.

        Returns:
            True.
        """
        self.calls.append(("click", selector))
        return True

    def reload(self) -> None:
        """Record a reload by the harness; the document token goes."""
        self.calls.append(("reload",))
        self.token = None

    def raise_errors(self) -> None:
        """No page errors."""

    def drain_console(self) -> dict[str, int]:
        """Report console messages.

        Returns:
            One warning.
        """
        return {"warning": 1}

    def close(self) -> None:
        """Record the close."""
        self.closed = True


class FakeCdp:
    """Records CDP commands."""

    def __init__(self, calls: list[tuple[Any, ...]]) -> None:
        """Share the page's call log.

        Args:
            calls: The log.
        """
        self.calls = calls

    def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Record a command.

        Args:
            method: The CDP method.
            params: Its parameters.

        Returns:
            An empty result.
        """
        self.calls.append(("cdp", method, params))
        return {}


class FakeBrowser:
    """Opens fake pages; ``owner`` decides whether the calling thread owns it."""

    created: list[FakeBrowser] = []
    values: dict[str, str] = {}
    tab_class: type[FakeTab] = FakeTab
    configure: Callable[[FakeTab], None] | None = None

    def __init__(self, *, headless: bool = True, cpu_throttle: int = 1) -> None:
        """Remember the settings.

        Args:
            headless: Unused.
            cpu_throttle: The CPU slowdown.
        """
        self.cpu_throttle = cpu_throttle
        self.anchor: Anchor | None = None
        self.owner = True
        self.closed = False
        self.killed = False
        self.tabs: list[FakeTab] = []
        FakeBrowser.created.append(self)

    def start(self) -> None:
        """Take the clock anchor."""
        self.anchor = Anchor.take()

    def interactive(self, app: FakeApp, path: str = "/") -> Interactive:
        """Open a page, as the real one does, and fill tier 3.

        Args:
            app: The app.
            path: The page path.

        Returns:
            Tier 3 and the page.
        """
        app.calls.append(f"interactive {path}")
        assert app.readiness is not None
        app.readiness.interactive_ready = 3.0
        tab = self.tab_class(app, FakeBrowser.values)
        if FakeBrowser.configure is not None:
            FakeBrowser.configure(tab)
        self.tabs.append(tab)
        return Interactive(
            tab=tab,  # pyright: ignore[reportArgumentType]
            interactive_ready=3.0,
            nav_to_interactive_s=0.8,
            fcp_s=2.5,
            lcp_s=2.6,
        )

    def owns_thread(self) -> bool:
        """Tell whether the calling thread may use the browser.

        Returns:
            ``owner``.
        """
        return self.owner

    def close_tab(self, tab: FakeTab) -> None:
        """Close a page, or kill the browser from a foreign thread.

        Args:
            tab: The page.
        """
        if self.owner:
            tab.close()
        else:
            self.kill()

    def close(self) -> None:
        """Record the close."""
        self.closed = True

    def kill(self) -> None:
        """Record the kill."""
        self.killed = self.closed = True
