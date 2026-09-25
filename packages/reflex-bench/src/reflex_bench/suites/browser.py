"""Browser benchmarks: when a started app is interactive in a browser, and prod page loads.

Every benchmark here runs the playground staged in its cache directory
(:func:`reflex_bench.fixtures.prime`), compiled once so starts are warm. Tier 3
(``interactive_ready``) is when the page itself showed ``#bench-hydrated``: the
websocket connected and the first state update applied.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from reflex_bench.context import Context
from reflex_bench.drivers.app_process import AppProcess, Mode
from reflex_bench.drivers.browser import Browser, Tab
from reflex_bench.fixtures import (
    app_dir,
    app_env,
    describe_playground,
    fixture_hash,
    prime,
)
from reflex_bench.registry import Metric, SampleResult, benchmark

APP_TIMEOUT_S = 600.0
# The main thread budget of a task; what a long task takes beyond it blocks input.
BLOCKING_MS = 50.0

READY_METRICS = {
    name: Metric(unit="s", direction="lower", description=description)
    for name, description in (
        ("process_ready", "spawn to ready lines and open ports (tier 1)"),
        ("http_ready", "spawn to GET / answering 200 (tier 2)"),
        ("interactive_ready", "spawn to the page showing #bench-hydrated (tier 3)"),
        ("nav_to_interactive", "navigation start to #bench-hydrated, in the page"),
        ("fcp", "spawn to the first contentful paint"),
    )
}


def total_blocking_time(
    tasks: Iterable[Mapping[str, float]], interactive_ms: float
) -> float:
    """Sum what long tasks blocked the main thread before the page was interactive.

    Args:
        tasks: Long tasks, ``{"start", "duration"}`` in ms since navigation start.
        interactive_ms: When the page was interactive, in ms since navigation start.

    Returns:
        Seconds: the sum of ``duration - 50 ms`` over the long tasks that started
        before ``interactive_ms``.
    """
    return (
        sum(
            max(0.0, task["duration"] - BLOCKING_MS)
            for task in tasks
            if task["start"] < interactive_ms
        )
        / 1000
    )


class _Ready:
    """Start the app with `reflex run` and open it in a fresh page, per sample.

    The app starts per sample (during `ab` both arms' sessions are open, so
    nothing heavy lives between samples); the browser lives for the instance.
    """

    mode: Mode = "dev"
    browser: Browser | None = None
    app: AppProcess | None = None
    tab: Tab | None = None

    def setup_cache(self, ctx: Context) -> None:
        """Stage and compile the playground.

        Args:
            ctx: The benchmark context.
        """
        prime(ctx)

    def setup(self, ctx: Context) -> None:
        """Record the fixture and start the browser.

        Args:
            ctx: The benchmark context.
        """
        ctx.fixture = describe_playground()
        browser = self.browser = Browser()
        browser.start()

    def sample(self, ctx: Context) -> SampleResult:
        """Start the app and wait for the three readiness tiers; conclude() stops it.

        Args:
            ctx: The benchmark context.

        Returns:
            The tiers in seconds since the spawn, with their gaps and the
            fixture's content hash as extra data.
        """
        browser = self.browser
        assert browser is not None
        app_path = app_dir(ctx)
        # conclude() may run on another thread after a timeout and clear these.
        app = self.app = AppProcess(
            ctx.subject.python,
            app_path,
            mode=self.mode,
            reflex_version=ctx.subject.reflex_version,
            env=app_env(ctx, app_path),
        )
        readiness = app.start()
        http_ready = app.wait_http_ready()
        result = browser.interactive(app)
        tab = self.tab = result.tab
        tab.raise_errors()
        return SampleResult(
            {
                "process_ready": readiness.process_ready,
                "http_ready": http_ready,
                "interactive_ready": result.interactive_ready,
                "nav_to_interactive": result.nav_to_interactive_s,
                "fcp": result.fcp_s,
            },
            extra={
                "gaps": {
                    "http_after_process_s": http_ready - readiness.process_ready,
                    "interactive_after_http_s": result.interactive_ready - http_ready,
                },
                "lcp_s": result.lcp_s,
                "console": tab.drain_console(),
                "anchor_spread_s": browser.anchor.spread if browser.anchor else None,
                "fixture_hash": fixture_hash("playground"),
            },
        )

    def conclude(self, ctx: Context) -> None:
        """Close the page, then kill the app's process tree, also after a failure.

        Args:
            ctx: The benchmark context.
        """
        browser, tab, app = self.browser, self.tab, self.app
        self.tab = self.app = None
        try:
            if browser is not None and tab is not None:
                browser.close_tab(tab)
        finally:
            if app is not None:
                app.stop()

    def cleanup(self, ctx: Context) -> None:
        """Close the browser.

        Args:
            ctx: The benchmark context.
        """
        if self.browser is not None:
            self.browser.close()


@benchmark(
    id="browser.dev.ready",
    suites=("pr", "daily"),
    kind="startup",
    metrics=READY_METRICS,
    warmup=1,
    timeout=APP_TIMEOUT_S,
    setup_timeout=APP_TIMEOUT_S + 60,
    estimate=8,
)
class DevReady(_Ready):
    """Start the playground with `reflex run` (dev) until it is interactive in a browser."""

    mode = "dev"


@benchmark(
    id="browser.preview.ready",
    suites=("daily",),
    kind="startup",
    metrics=READY_METRICS,
    warmup=1,
    timeout=APP_TIMEOUT_S,
    setup_timeout=APP_TIMEOUT_S + 60,
    estimate=30,
    min_version="0.9.8",
)
class PreviewReady(_Ready):
    """Start the playground with `reflex run --env preview` until it is interactive."""

    mode = "preview"


@benchmark(
    id="browser.prod.ready",
    suites=("daily",),
    kind="startup",
    metrics=READY_METRICS,
    warmup=1,
    timeout=APP_TIMEOUT_S,
    setup_timeout=APP_TIMEOUT_S + 60,
    estimate=40,
)
class ProdReady(_Ready):
    """Start the playground with `reflex run --env prod` until it is interactive.

    A prod start includes the frontend build. 0.8.x serves the build with sirv on
    its own port and the backend on another; the driver handles both topologies.
    """

    mode = "prod"


@benchmark(
    id="browser.prod.pageload",
    suites=("daily",),
    kind="latency",
    params={"cpu": [1, 4]},
    metrics={
        "fcp": Metric(
            unit="s", direction="lower", description="first contentful paint"
        ),
        "lcp": Metric(
            unit="s", direction="lower", description="largest contentful paint"
        ),
        "interactive": Metric(
            unit="s",
            direction="lower",
            description="navigation start to #bench-hydrated",
        ),
        "tbt": Metric(
            unit="s",
            direction="lower",
            description="total blocking time before interactive",
        ),
        "ws_bytes": Metric(
            unit="B",
            direction="lower",
            assume="exact",
            description="websocket payload bytes",
        ),
        "transfer_bytes": Metric(
            unit="B",
            direction="lower",
            assume="exact",
            description="HTTP response bytes over the wire, headers included",
        ),
    },
    warmup=1,
    timeout=120,
    setup_timeout=APP_TIMEOUT_S + 60,
    estimate=3,
)
class ProdPageload:
    """Load / of the prod playground in a fresh browser context (cold cache), CPU optionally throttled.

    One prod server serves every sample of an instance on purpose: a prod start
    includes a full frontend build, and during `ab` the other arm's idle server
    does not touch page load. The times are page-relative (ms since navigation
    start, stored in seconds), read as soon as the page is interactive; on the
    playground the first contentful paint is also the largest, so ``fcp`` and
    ``lcp`` coincide. Page loads are noisy: read the median and its confidence
    interval over at least 6 runs; outliers are counted, not dropped.
    """

    app: AppProcess | None = None
    browser: Browser | None = None
    tab: Tab | None = None

    def setup_cache(self, ctx: Context) -> None:
        """Stage and compile the playground.

        Args:
            ctx: The benchmark context.
        """
        prime(ctx)

    def setup(self, ctx: Context) -> None:
        """Record the fixture and start the prod app and the browser.

        Args:
            ctx: The benchmark context.
        """
        ctx.fixture = describe_playground()
        app_path = app_dir(ctx)
        app = self.app = AppProcess(
            ctx.subject.python,
            app_path,
            mode="prod",
            reflex_version=ctx.subject.reflex_version,
            env=app_env(ctx, app_path),
        )
        app.start()
        app.wait_http_ready()
        browser = self.browser = Browser(cpu_throttle=ctx.params["cpu"])
        browser.start()

    def sample(self, ctx: Context) -> SampleResult:
        """Load / until it is interactive and read its timings.

        Args:
            ctx: The benchmark context.

        Returns:
            Paint times, time to interactive and total blocking time in seconds
            since navigation start, and the bytes the page received.

        Raises:
            RuntimeError: When the page reported no largest contentful paint.
        """
        browser, app = self.browser, self.app
        assert browser is not None
        assert app is not None
        result = browser.interactive(app)
        tab = self.tab = result.tab
        timings = tab.timings()
        tab.raise_errors()
        if timings["lcp"] is None:
            msg = "the page reported no largest contentful paint"
            raise RuntimeError(msg)
        interactive_ms = result.nav_to_interactive_s * 1000
        return SampleResult(
            {
                "fcp": timings["fcp"] / 1000,
                "lcp": timings["lcp"] / 1000,
                "interactive": result.nav_to_interactive_s,
                "tbt": total_blocking_time(timings["longtasks"], interactive_ms),
                "ws_bytes": tab.ws_bytes,
                "transfer_bytes": tab.transfer_bytes,
            },
            extra={
                "cpu": ctx.params["cpu"],
                "long_tasks": len(timings["longtasks"]),
                "long_animation_frames": len(timings["loafs"]),
                "console": tab.drain_console(),
                "fixture_hash": fixture_hash("playground"),
            },
        )

    def conclude(self, ctx: Context) -> None:
        """Close the page's browser context.

        Args:
            ctx: The benchmark context.
        """
        browser, tab = self.browser, self.tab
        self.tab = None
        if browser is not None and tab is not None:
            browser.close_tab(tab)

    def cleanup(self, ctx: Context) -> None:
        """Close the browser and kill the app's process tree.

        Args:
            ctx: The benchmark context.
        """
        try:
            if self.browser is not None:
                self.browser.close()
        finally:
            if self.app is not None:
                self.app.stop()
