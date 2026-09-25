"""Hot reload benchmarks: from an edit of the app's source to the page showing it.

An instance runs one app and one page for all its samples, against the
README's "keep heavy processes per sample" rule, on purpose: a dev start plus
hydration before every edit would multiply the run time by about ten, and
during `ab` the other arm's server only idles while this one recompiles.

A sample:

1. ``prepare`` waits until the page is quiet (no pending watch, no DOM change
   for :data:`QUIET_S`), tags the document (``__BENCH_ALIVE``), builds the
   edit's new content in memory and arms the page's watch for its unique value;
2. ``sample`` writes the edit (``t0`` is taken just before the one
   ``os.replace``) and returns as soon as the page's mark is there: ``latency``
   is the mark's ``Date.now()`` minus ``t0``, both on the wall clock, and the
   mark's copy of the tag tells whether the page reloaded to show the edit;
3. ``conclude`` waits until the page is quiet again and reads the tag back (a
   reload right after a hot update must not pass for one), restores the file
   and waits until the page shows the original again and is quiet.

A lost tag means the page reloaded instead of updating, counted in
``full_reloads``. For the render, handler and reconnect benchmarks that is no
hot reload sample: ``conclude`` fails it with :class:`FullReloadError`, so
``latency`` only ever holds a hot update. For the style benchmark the change
may only show through a reload: ``latency`` is the time until it shows by
whatever means. A change a dev page never shows by itself (no hot update, no
reload) fails the sample, saying what the backend and the page did meanwhile
(:func:`describe_miss`); a stylesheet hot update vite delivered that the page
did not apply within :data:`APPLY_S` fails it at once
(:class:`DroppedUpdateError`) instead of waiting the deadline out. Every hook's
waits share one deadline, :data:`WAIT_S` after the hook started, within the
hooks' :data:`TIMEOUT_S`.

Vite has no module for a file of ``public/`` (an asset), so a change to one
reaches no page: the asset benchmark refreshes the page every :data:`POLL_S`
until it shows the new file, as a user would, in every mode.

Preview mode (reflex 0.9.8+) serves a static build: a hot reload rebuilds it,
and it shows after a refresh. Preview benchmarks whose change needs a new page
reload it every :data:`POLL_S` until it shows, so their ``latency`` includes the
rebuild and the refresh, and ``full_reloads`` stays 0.

Backend hops, in seconds since the edit, are stored per sample in
``extra["hops"]``: ``watcher_seen_s`` (granian's ``Changes detected`` line),
``compile_done_s`` (the reload's last ``[timing]`` line) and ``dom_updated_s``
(the page's mark).
"""

from __future__ import annotations

import contextlib
import re
import signal
import time
import urllib.parse
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

import psutil

from reflex_bench.context import Context
from reflex_bench.drivers.app_process import AppProcess, Mode
from reflex_bench.drivers.browser import Browser, Mark, Tab
from reflex_bench.drivers.editor import Edit, Target, find_target, text_target
from reflex_bench.fixtures import FIXTURES, app_dir, app_env, fixture_hash, prime
from reflex_bench.registry import Metric, SampleResult, benchmark

# The wait between edits: how long the page must be quiet before an edit and
# after its restore.
QUIET_S = 0.5
# How often a page is clicked or reloaded until it shows an edit.
POLL_S = 0.25
# The most a hook waits for the page, all its waits together, within the
# hooks' TIMEOUT_S.
WAIT_S = 90.0
# How long the page gets to apply a hot update vite delivered before the
# update counts as dropped.
APPLY_S = 5.0
TIMEOUT_S = 120.0
SETUP_TIMEOUT_S = 660.0
# Loose on purpose: granian versions may word their reload line differently.
WATCHER = re.compile(r"Changes detected")
# Vite's log line for a hot update it sent, e.g. "[vite] (client) hmr update
# /styles/__reflex_global_styles.css?direct" (the path may wrap onto the next
# line).
VITE_UPDATE = re.compile(r"\[vite\].*hmr update")
TIMING = "[timing]"
# Log line times and the edit's time come from different clocks, mapped onto
# each other with millisecond resolution.
_CLOCK_SLACK_S = 0.005

_T = TypeVar("_T", bound=type)

METRICS = {
    "latency": Metric(
        unit="s", direction="lower", description="edit written to the page showing it"
    ),
    "full_reloads": Metric(
        unit="1", direction="lower", description="page reloads instead of hot updates"
    ),
}


class FullReloadError(RuntimeError):
    """The page reloaded instead of applying a hot update."""


class DroppedUpdateError(RuntimeError):
    """Vite delivered a hot update the page did not apply."""


def _deadline() -> float:
    """Start a hook's wait budget.

    Returns:
        ``time.monotonic()`` plus :data:`WAIT_S`.
    """
    return time.monotonic() + WAIT_S


def _left(deadline: float) -> float:
    """Tell how long a wait may still take.

    Args:
        deadline: The hook's deadline.

    Returns:
        Seconds until it.

    Raises:
        TimeoutError: When it passed.
    """
    left = deadline - time.monotonic()
    if left <= 0:
        msg = f"the page kept the hook waiting for more than {WAIT_S:g} s"
        raise TimeoutError(msg)
    return left


def watcher_line(
    lines: Sequence[tuple[float, str]], edit_at: float
) -> tuple[float, str] | None:
    """Find granian's reload line for an edit.

    Args:
        lines: The app's log lines, with their times since the app's t0.
        edit_at: When the edit was written, in seconds since the app's t0.

    Returns:
        The first ``Changes detected`` line after the edit, with its time.
    """
    return next(
        (
            (at, line)
            for at, line in lines
            if at >= edit_at - _CLOCK_SLACK_S and WATCHER.search(line)
        ),
        None,
    )


def hops(
    lines: Sequence[tuple[float, str]],
    edit_at: float,
    dom_updated_s: float | None,
    watcher: tuple[float, str] | None,
) -> dict[str, float | None]:
    """Time the steps of the reload an edit caused.

    Args:
        lines: The app's log lines, with their times since the app's t0.
        edit_at: When the edit was written, in seconds since the app's t0.
        dom_updated_s: When the page showed the edit, in seconds since the edit
            (``None``: it did not).
        watcher: The edit's :func:`watcher_line`.

    Returns:
        ``watcher_seen_s``, ``compile_done_s`` (the last ``[timing]`` line after
        the watcher's, or after the edit without one) and ``dom_updated_s``, in
        seconds since the edit; ``None`` for a step the log does not show.
    """
    start = edit_at if watcher is None else watcher[0]
    timing = [at for at, line in lines if at > start and TIMING in line]
    return {
        "watcher_seen_s": None if watcher is None else watcher[0] - edit_at,
        "compile_done_s": timing[-1] - edit_at if timing else None,
        "dom_updated_s": dom_updated_s,
    }


def describe_miss(steps: dict[str, float | None], reloaded: bool | None) -> str:
    """Say what the backend and the page did with a change the page never showed.

    Args:
        steps: The change's :func:`hops`.
        reloaded: Whether the page reloaded meanwhile; ``None`` when the harness
            reloads it itself.

    Returns:
        The facts, e.g. ``granian saw it after 0.15 s, the last [timing] line
        came after 1.19 s, the page did not reload``.
    """
    seen, done = steps["watcher_seen_s"], steps["compile_done_s"]
    facts = [
        "granian printed no reload line"
        if seen is None
        else f"granian saw it after {seen:.2f} s",
        "no [timing] line followed"
        if done is None
        else f"the last [timing] line came after {done:.2f} s",
    ]
    if reloaded is not None:
        facts.append("the page reloaded" if reloaded else "the page did not reload")
    return ", ".join(facts)


def granian_processes(app: AppProcess) -> tuple[psutil.Process, psutil.Process]:
    """Find granian's supervisor and worker in a dev (or preview) app.

    ``reflex run`` runs granian's supervisor in its own main thread; the worker
    is the process of the tree, other than that root, listening on the backend
    port. (The tree also holds the frontend and, with Python 3.14,
    multiprocessing's resource tracker and forkserver.)

    Args:
        app: The started app.

    Returns:
        ``(supervisor, worker)``.

    Raises:
        LookupError: When no process of the app listens on the backend port.
    """
    port = urllib.parse.urlsplit(app.backend_url).port
    root = psutil.Process(app.pid)
    for proc in root.children(recursive=True):
        with contextlib.suppress(psutil.Error):
            if any(
                conn.status == psutil.CONN_LISTEN and conn.laddr.port == port
                for conn in proc.net_connections("tcp")
            ):
                return root, proc
    msg = f"no process of the app listens on the backend port {port} besides its root"
    raise LookupError(msg)


class _HotReload:
    """Edit the staged app and wait for the page to show it; see the module docstring."""

    mode: Mode = "dev"
    # The page the benchmark watches, and what its watch compares.
    path = "/"
    kind = "text"
    selector = "#bench-marker-leaf"
    # A reload means the edit was no hot update: the sample fails.
    hot_update_only = True
    # Clicked every POLL_S until the page shows the edit, for a change that
    # only shows through an event.
    click: str | None = None

    app: AppProcess | None = None
    browser: Browser | None = None
    tab: Tab | None = None
    edit: Edit | None = None
    original: str | None = None
    alive: str | None = None
    expected: str | None = None
    # Whether the last sample's page reloaded; None until the sample returned.
    reloaded: bool | None = None
    edits = 0

    @property
    def reloads_itself(self) -> bool:
        """Whether the harness reloads the page to show a change (preview's static build).

        Returns:
            True in preview mode for a change that needs a new page.
        """
        return self.mode == "preview" and self.click is None

    def target(self, app: Path) -> Target | None:
        """Find the text the benchmark rewrites.

        Args:
            app: The staged app.

        Returns:
            The target, or ``None`` for a benchmark that edits nothing.
        """
        return find_target(app, "leaf")

    def original_value(self, tab: Tab, deadline: float) -> str | None:
        """Tell what the page shows for the unedited app, once it has settled.

        Args:
            tab: The page.
            deadline: The hook's deadline.

        Returns:
            The value a restore brings back.
        """
        # Stylesheets and images may still load after the page is hydrated.
        tab.wait_quiet(QUIET_S, _left(deadline))
        return tab.wait_value(self.kind, self.selector, _left(deadline))

    def plan(self) -> str:
        """Build the next edit's content.

        Returns:
            What the page shows once the edit is applied: a new marker.
        """
        marker = f"m-{uuid.uuid4().hex[:12]}"
        assert self.edit is not None
        self.edit.prepare(marker)
        return marker

    def trigger(self) -> int:
        """Make the change.

        Returns:
            ``time.time_ns()`` just before it.
        """
        assert self.edit is not None
        return self.edit.write()

    def latency(self, mark: Mark, t0: int, steps: dict[str, float | None]) -> float:
        """Compute the sample's latency.

        Args:
            mark: The page's mark of the change.
            t0: ``time.time_ns()`` just before the change.
            steps: The backend hops.

        Returns:
            Seconds from the change to the page showing it.
        """
        return mark["epoch"] / 1000 - t0 / 1e9

    def extras(self, tab: Tab) -> dict[str, Any]:
        """Add variant-specific data to a sample.

        Args:
            tab: The page.

        Returns:
            Extra data.
        """
        return {}

    def setup_cache(self, ctx: Context) -> None:
        """Stage and compile the fixture app.

        Args:
            ctx: The benchmark context.
        """
        prime(ctx, ctx.params["app"])

    def setup(self, ctx: Context) -> None:
        """Start the app with debug logs and open its page until it is hydrated.

        Args:
            ctx: The benchmark context.
        """
        app_path = app_dir(ctx)
        target = self.target(app_path)
        if target is not None:
            self.edit = Edit(target)
        app = self.app = AppProcess(
            ctx.subject.python,
            app_path,
            mode=self.mode,
            reflex_version=ctx.subject.reflex_version,
            env=app_env(ctx, app_path),
            phases=True,
        )
        app.start()
        app.wait_http_ready()
        browser = self.browser = Browser()
        browser.start()
        tab = self.tab = browser.interactive(app, self.path).tab
        self.original = self.original_value(tab, _deadline())

    def prepare(self, ctx: Context) -> None:
        """Wait for a quiet page, tag the document and arm the watch of a new edit.

        Args:
            ctx: The benchmark context.
        """
        tab = self.tab
        assert tab is not None
        tab.wait_quiet(QUIET_S, _left(_deadline()))
        tab.drain_console()
        self.alive = tab.set_alive()
        self.reloaded = None
        self.edits += 1
        self.expected = self.plan()
        tab.watch("edit", self.kind, self.selector, self.expected)

    def _until(self, tab: Tab, id: str, t0: int, deadline: float) -> tuple[Mark, int]:
        """Wait for a mark, clicking or reloading every POLL_S when the change needs it.

        Args:
            tab: The page.
            id: The mark id.
            t0: ``time.time_ns()`` just before the change.
            deadline: The hook's deadline.

        Returns:
            The mark, and the clicks or reloads it took.

        Raises:
            TimeoutError: When the page does not show the change before the
                deadline, with what the backend and the page did meanwhile.
            DroppedUpdateError: When the page can no longer show the change
                (:meth:`dropped`).
        """
        count = 0
        mark = None
        if self.click is None and not self.reloads_itself:
            while mark is None and (left := deadline - time.monotonic()) > 0:
                mark = tab.poll_mark(id, min(POLL_S, left))
                if mark is None and (why := self.dropped(tab, t0)) is not None:
                    msg = f"the page did not show the {id} ({self.kind} of {self.selector}): {why}"
                    raise DroppedUpdateError(msg)
        else:
            while mark is None and (left := deadline - time.monotonic()) > 0:
                if self.click is None:
                    tab.reload()
                else:
                    tab.click(self.click)
                count += 1
                mark = tab.poll_mark(id, min(POLL_S, left))
        if mark is None:
            how = ""
            if self.click is not None:
                how = f" while clicking {self.click}"
            elif self.reloads_itself:
                how = " while refreshing it"
            edit_at, lines = self._log_since(t0)
            facts = describe_miss(
                hops(lines, edit_at, None, watcher_line(lines, edit_at)),
                None if self.reloads_itself else tab.alive() != self.alive,
            )
            msg = (
                f"the page did not show the {id} ({self.kind} of {self.selector})"
                f" within the hook's {WAIT_S:g} s{how}: {facts}; the page shows"
                f" {tab.read(self.kind, self.selector)!r}"
            )
            raise TimeoutError(msg)
        return mark, count

    def dropped(self, tab: Tab, t0: int) -> str | None:
        """Tell whether the page can no longer show a change by itself.

        Args:
            tab: The page.
            t0: ``time.time_ns()`` just before the change.

        Returns:
            What happened, or ``None`` while the change may still show.
        """
        return None

    def _log_since(self, t0: int) -> tuple[float, list[tuple[float, str]]]:
        """Read the app's log and place a change on its clock.

        Args:
            t0: ``time.time_ns()`` just before the change.

        Returns:
            When the change happened, in seconds since the app's t0, and the
            log lines with their times.
        """
        app, browser = self.app, self.browser
        assert app is not None
        assert browser is not None
        assert browser.anchor is not None
        return browser.anchor.perf_at(t0 / 1e9) - app.t0, app.log_lines()

    def sample(self, ctx: Context) -> SampleResult:
        """Make the change and return once the page shows it.

        Args:
            ctx: The benchmark context.

        Returns:
            The latency and whether the page reloaded to show the change, with
            the hops as extra data.
        """
        browser, tab = self.browser, self.tab
        assert browser is not None
        assert browser.anchor is not None
        assert tab is not None
        deadline = _deadline()
        t0 = self.trigger()
        mark, repeats = self._until(tab, "edit", t0, deadline)
        edit_at, lines = self._log_since(t0)
        watcher = watcher_line(lines, edit_at)
        steps = hops(lines, edit_at, mark["epoch"] / 1000 - t0 / 1e9, watcher)
        tab.raise_errors()
        reloaded = self.reloaded = (
            not self.reloads_itself and mark["alive"] != self.alive
        )
        extra: dict[str, Any] = {
            "marker": self.expected,
            "hops": steps,
            "watcher_line": None if watcher is None else watcher[1],
            "console": tab.drain_console(),
            "anchor_spread_s": browser.anchor.spread,
            "fixture_hash": fixture_hash(ctx.params["app"]),
            **self.extras(tab),
        }
        if self.click is not None:
            extra["clicks"] = repeats
        elif self.reloads_itself:
            extra["reloads"] = repeats
        return SampleResult(
            {
                "latency": self.latency(mark, t0, steps),
                "full_reloads": int(reloaded),
            },
            extra,
        )

    def conclude(self, ctx: Context) -> None:
        """Restore the file and wait until the page shows the original and is quiet.

        From a thread that does not own the browser (after a timeout the sample
        is still blocked in the page on the owner thread), restores the file
        and kills the browser, which ends the blocked wait.

        Args:
            ctx: The benchmark context.

        Raises:
            FullReloadError: When the page reloaded instead of applying the hot
                update, also right after showing it.
        """
        edit, tab, browser = self.edit, self.tab, self.browser
        if browser is None or tab is None or not browser.owns_thread():
            if edit is not None and edit.edited:
                edit.restore()
            if browser is not None and not browser.owns_thread():
                browser.kill()
            return
        deadline = _deadline()
        # A change the page never showed must not stay pending.
        tab.unwatch("edit")
        # Only a returned sample of a hot update has a document to check.
        check = (
            self.hot_update_only
            and not self.reloads_itself
            and self.reloaded is not None
        )
        reloaded = self.reloaded
        if check and not reloaded:
            tab.wait_quiet(QUIET_S, _left(deadline))
            reloaded = tab.alive() != self.alive
        if edit is not None and edit.edited:
            restored_at = edit.restore()
            tab.watch("restore", self.kind, self.selector, self.original)
            self._until(tab, "restore", restored_at, deadline)
        tab.wait_quiet(QUIET_S, _left(deadline))
        if check and reloaded:
            msg = "the page reloaded instead of applying the hot update"
            raise FullReloadError(msg)

    def cleanup(self, ctx: Context) -> None:
        """Restore an edit left behind, close the browser and stop the app.

        Args:
            ctx: The benchmark context.
        """
        with contextlib.ExitStack() as stack:
            if self.app is not None:
                stack.callback(self.app.stop)
            if self.browser is not None:
                stack.callback(self.browser.close)
            if self.edit is not None and self.edit.edited:
                self.edit.restore()


def _hmr(
    id: str, *, suites: Sequence[str] = ("daily",), estimate: float = 4.0
) -> Callable[[_T], _T]:
    """Declare a hot reload benchmark; ids ending in ``.preview`` need reflex 0.9.8.

    Args:
        id: The benchmark id.
        suites: Its suites.
        estimate: Rough seconds per sample.

    Returns:
        The class decorator.
    """
    return benchmark(
        id=id,
        suites=suites,
        kind="latency",
        params={"app": list(FIXTURES)},
        metrics=METRICS,
        warmup=3,
        timeout=TIMEOUT_S,
        setup_timeout=SETUP_TIMEOUT_S,
        estimate=estimate,
        min_version="0.9.8" if id.endswith(".preview") else None,
    )


# Preview rebuilds the frontend on every reload: seconds per edit and restore.
PREVIEW_ESTIMATE_S = 30.0


@_hmr("hmr.render.leaf", suites=("pr", "daily"))
class RenderLeaf(_HotReload):
    """Rewrite the leaf marker, rendered by the index page only, until the page shows it."""


@_hmr("hmr.render.leaf.preview", estimate=PREVIEW_ESTIMATE_S)
class RenderLeafPreview(RenderLeaf):
    """Rewrite the leaf marker in preview mode, refreshing until the page shows it."""

    mode = "preview"


@_hmr("hmr.render.root", suites=("pr", "daily"))
class RenderRoot(_HotReload):
    """Rewrite the root marker, which every page renders, until the page shows it."""

    selector = "#bench-marker-root"

    def target(self, app: Path) -> Target:
        """Find the root marker.

        Args:
            app: The staged app.

        Returns:
            The ``ROOT_MARKER`` literal.
        """
        return find_target(app, "root")


@_hmr("hmr.render.root.preview", estimate=PREVIEW_ESTIMATE_S)
class RenderRootPreview(RenderRoot):
    """Rewrite the root marker in preview mode, refreshing until the page shows it."""

    mode = "preview"


@_hmr("hmr.handler", suites=("pr", "daily"))
class Handler(_HotReload):
    """Rewrite what an event handler sets, clicking its button until the page shows it."""

    selector = "#bench-handler-value"
    click = "#bench-handler"

    def target(self, app: Path) -> Target:
        """Find the handler marker.

        Args:
            app: The staged app.

        Returns:
            The ``HANDLER_MARKER`` literal.
        """
        return find_target(app, "handler")

    def original_value(self, tab: Tab, deadline: float) -> str | None:
        """Tell what a click shows with the unedited handler.

        Args:
            tab: The page.
            deadline: The hook's deadline.

        Returns:
            The handler marker's original literal.
        """
        assert self.edit is not None
        return self.edit.target.literal


@_hmr("hmr.handler.preview", estimate=PREVIEW_ESTIMATE_S)
class HandlerPreview(Handler):
    """Rewrite what an event handler sets in preview mode, clicking until the page shows it."""

    mode = "preview"


@_hmr("hmr.css")
class Css(_HotReload):
    """Change the font size of the benchmark hooks in the app's stylesheet until the page shows it."""

    kind = "style:font-size"
    selector = ".bench-hooks"
    hot_update_only = False

    def target(self, app: Path) -> Target:
        """Find the hooks' font size.

        Args:
            app: The staged app.

        Returns:
            The ``font-size`` value of ``.bench-hooks`` in ``assets/playground.css``.
        """
        return text_target(
            app / "assets" / "playground.css", "0.75rem", after=".bench-hooks {"
        )

    def plan(self) -> str:
        """Pick a new font size, a different one for each of 160 edits.

        Returns:
            The size, in the ``px`` the computed style reports (quarter pixels
            serialize exactly).
        """
        size = f"{20 + self.edits % 160 / 4:g}px"
        if size == self.original:
            size = f"{61 + self.edits % 160 / 4:g}px"
        assert self.edit is not None
        self.edit.prepare(size)
        return size

    def dropped(self, tab: Tab, t0: int) -> str | None:
        """Tell whether vite's hot update of the stylesheet came and went unapplied.

        Args:
            tab: The page.
            t0: ``time.time_ns()`` just before the change.

        Returns:
            The facts once vite logged the update :data:`APPLY_S` ago and the
            page neither shows the value nor reloaded; ``None`` before that.
        """
        edit_at, lines = self._log_since(t0)
        update = next(
            (
                at
                for at, line in lines
                if at >= edit_at - _CLOCK_SLACK_S and VITE_UPDATE.search(line)
            ),
            None,
        )
        if update is None:
            return None
        assert self.app is not None
        ago = time.perf_counter() - self.app.t0 - update
        if ago < APPLY_S or tab.alive() != self.alive:
            return None
        return (
            f"vite sent the stylesheet's hot update {ago:.1f} s ago"
            f" ({update - edit_at:.2f} s after the edit) but the page did not"
            f" apply it: {self.kind[6:]} of {self.selector} is still"
            f" {tab.read(self.kind, self.selector)!r}, the page did not reload"
        )


@_hmr("hmr.css.preview", estimate=PREVIEW_ESTIMATE_S)
class CssPreview(Css):
    """Change the hooks' font size in preview mode, refreshing until the page shows it."""

    mode = "preview"


@_hmr("hmr.asset")
class Asset(_HotReload):
    """Give the benchmark mark an intrinsic size, refreshing until the page shows the new image.

    Vite has no module for a file of ``public/``, so the change reaches no
    page: the harness refreshes every :data:`POLL_S` (``extra["reloads"]``),
    as a user would, and ``latency`` is the time until a refresh shows the new
    file. The browser cache is off for this page, so a refresh fetches it.
    """

    kind = "naturalWidth"
    selector = "#bench-mark"

    @property
    def reloads_itself(self) -> bool:
        """The harness refreshes the page in every mode.

        Returns:
            True.
        """
        return True

    def target(self, app: Path) -> Target:
        """Find the mark's root element.

        Args:
            app: The staged app.

        Returns:
            The ``<svg`` of ``assets/mark.svg``, which has only a viewBox.
        """
        return text_target(app / "assets" / "mark.svg", "<svg")

    def setup(self, ctx: Context) -> None:
        """Open the page and turn its HTTP cache off.

        Args:
            ctx: The benchmark context.
        """
        super().setup(ctx)
        assert self.tab is not None
        self.tab.cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})

    def plan(self) -> str:
        """Pick a new width and height, a different one for each of 400 edits.

        Returns:
            The image's natural width once the new file is loaded.
        """
        width = 41 + self.edits % 400
        if str(width) == self.original:
            width += 400
        assert self.edit is not None
        self.edit.prepare(f'<svg width="{width}" height="{width}"')
        return str(width)

    def extras(self, tab: Tab) -> dict[str, Any]:
        """Record that the cache was off.

        Args:
            tab: The page.

        Returns:
            ``cache_disabled``.
        """
        return {"cache_disabled": True}


@_hmr("hmr.asset.preview", estimate=PREVIEW_ESTIMATE_S)
class AssetPreview(Asset):
    """Give the mark an intrinsic size in preview mode, refreshing until the page shows it."""

    mode = "preview"


@_hmr("hmr.reconnect")
class Reconnect(_HotReload):
    """Kill granian's worker and click the counter until the page reaches the new one.

    granian's dev reloader never respawns a worker that died on its own (reflex
    runs it with ``reload_ignore_worker_failure``): after the SIGKILL, SIGHUP to
    its supervisor asks for the respawn a crash does not get. ``latency`` runs
    from the kill to the first change of the count.
    """

    path = "/counter"
    kind = "changed"
    selector = "#count"
    click = "#increment"
    processes: tuple[psutil.Process, psutil.Process] | None = None
    reload_events = 0

    def target(self, app: Path) -> None:
        """Edit nothing.

        Args:
            app: The staged app.
        """

    def plan(self) -> str:
        """Find the processes to signal, before the timed region.

        Returns:
            The count shown now; the watch waits for any other.
        """
        assert self.app is not None
        assert self.tab is not None
        self.processes = granian_processes(self.app)
        self.reload_events = self.tab.ws_events["reload"]
        return self.tab.read("text", self.selector) or ""

    def trigger(self) -> int:
        """Kill the worker, then ask the supervisor for a new one.

        Returns:
            ``time.time_ns()`` just before the kill.
        """
        assert self.processes is not None
        supervisor, worker = self.processes
        t0 = time.time_ns()
        worker.send_signal(signal.SIGKILL)
        supervisor.send_signal(signal.SIGHUP)
        return t0

    def extras(self, tab: Tab) -> dict[str, Any]:
        """Count the socket.io ``reload`` events the page got (reflex 0.8's re-hydration).

        Args:
            tab: The page.

        Returns:
            ``reload_events``.
        """
        return {"reload_events": tab.ws_events["reload"] - self.reload_events}


@_hmr("hmr.reconnect.preview", estimate=PREVIEW_ESTIMATE_S)
class ReconnectPreview(Reconnect):
    """Kill granian's worker in preview mode and click the counter until the page reaches the new one."""

    mode = "preview"


@_hmr("hmr.watcher")
class Watcher(RenderLeaf):
    """Rewrite the leaf marker and time granian's file watcher (``reload_tick`` is 100 ms).

    ``latency`` is the time from the edit to granian's ``Changes detected``
    line; the sample still waits for the page, so the next edit starts from a
    settled app. A full reload does not change the watcher's time, so it is only
    counted.
    """

    hot_update_only = False

    def latency(self, mark: Mark, t0: int, steps: dict[str, float | None]) -> float:
        """Take the watcher's time.

        Args:
            mark: The page's mark of the change.
            t0: ``time.time_ns()`` just before the change.
            steps: The backend hops.

        Returns:
            Seconds from the edit to granian's reload line.

        Raises:
            RuntimeError: When granian printed no reload line after the edit.
        """
        watcher_seen = steps["watcher_seen_s"]
        if watcher_seen is None:
            msg = "granian printed no 'Changes detected' line after the edit"
            raise RuntimeError(msg)
        return watcher_seen
