"""Production browser, bundle, hydration, and DOM-update benchmarks."""

from __future__ import annotations

import gzip
import os
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from reflex import constants
from reflex.testing import AppHarness
from tests.benchmarks.support import BenchmarkResult, PerformanceReport

# Gzip budget for the shipped client bundle. A fresh production export of the
# load app measured 238,635 gzip bytes (2026-07-13); the default budget is
# roughly double so only a real bundle regression trips it. CI can tune the
# budget without a code change via the environment variable.
MAX_JAVASCRIPT_GZIP_BYTES = int(
    os.environ.get("REFLEX_PERFORMANCE_JS_GZIP_BUDGET", 500_000)
)


def _bundle_metrics(root: Path) -> dict[str, int]:
    """Calculate shipped client-bundle module and compressed-size metrics.

    Only the exported client build (``.web/build/client``) is measured; the
    rest of ``.web`` is the build toolchain (``node_modules``, server bundles)
    that never reaches a browser.

    Args:
        root: Reflex application root.

    Returns:
        JavaScript module, raw byte, and gzip byte counts.
    """
    client = root / constants.Dirs.WEB / constants.Dirs.STATIC
    files = [
        path
        for path in client.rglob("*")
        if path.is_file() and path.suffix in {".js", ".mjs"}
    ]
    return {
        "javascript_modules": len(files),
        "javascript_bytes": sum(path.stat().st_size for path in files),
        "javascript_gzip_bytes": sum(
            len(gzip.compress(path.read_bytes())) for path in files
        ),
    }


def _browser_heap(page: Page) -> int:
    """Read Chromium's JavaScript heap metric.

    Args:
        page: Playwright page.

    Returns:
        Used JavaScript heap bytes, or zero if unavailable.
    """
    session = page.context.new_cdp_session(page)
    try:
        session.send("Performance.enable")
        metrics = session.send("Performance.getMetrics")["metrics"]
    finally:
        session.detach()
    values = {metric["name"]: metric["value"] for metric in metrics}
    return int(values.get("JSHeapUsedSize", 0))


@pytest.mark.performance
def test_browser_report(
    performance_load_app: AppHarness,
    page: Page,
    performance_output: Path,
    performance_scale: str,
):
    """Measure hydration, state-to-DOM updates, large lists, navigation, and heap.

    Args:
        performance_load_app: Running production app.
        page: Playwright browser page.
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    assert performance_load_app.frontend_url is not None
    page.add_init_script(
        """
        window.__reflexLongTasks = [];
        new PerformanceObserver((list) => {
          window.__reflexLongTasks.push(...list.getEntries().map((entry) => entry.duration));
        }).observe({entryTypes: ['longtask']});
        """
    )
    started = time.perf_counter_ns()
    page.goto(performance_load_app.frontend_url)
    # Gate on the websocket-driven is_hydrated marker, not the prerendered
    # #count text (which the static export already ships as "0"), so the timing
    # spans real hydration: connect, initial delta, and client state attach.
    expect(page.locator("#hydrated")).to_have_text("hydrated")
    expect(page.locator("#count")).to_have_text("0")
    hydration_ms = (time.perf_counter_ns() - started) / 1_000_000
    heap_before = _browser_heap(page)

    updates = {"smoke": 10, "release": 1000}[performance_scale]
    started = time.perf_counter_ns()
    for _ in range(updates):
        page.locator("#increment").click()
    expect(page.locator("#count")).to_have_text(str(updates))
    update_ms = (time.perf_counter_ns() - started) / 1_000_000

    started = time.perf_counter_ns()
    page.locator("#append-large").click()
    expect(page.locator(".value-row")).to_have_count(1000)
    large_list_ms = (time.perf_counter_ns() - started) / 1_000_000

    started = time.perf_counter_ns()
    page.locator("#second-link").click()
    expect(page.locator("#second-heading")).to_have_text("Second page")
    navigation_ms = (time.perf_counter_ns() - started) / 1_000_000
    heap_after = _browser_heap(page)
    long_tasks = page.evaluate("window.__reflexLongTasks || []")
    assert isinstance(long_tasks, list)

    metrics: dict[str, float | int] = dict(
        _bundle_metrics(performance_load_app.app_path)
    )
    metrics.update({
        "heap_before_bytes": heap_before,
        "heap_after_bytes": heap_after,
        "heap_growth_bytes": heap_after - heap_before,
        "long_task_count": len(long_tasks),
        "long_task_total_ms": sum(float(value) for value in long_tasks),
        "javascript_gzip_budget_bytes": MAX_JAVASCRIPT_GZIP_BYTES,
    })
    report = PerformanceReport(
        "browser",
        metadata={"scale": performance_scale},
    )
    for name, observations, parameters in [
        ("hydration", [hydration_ms], {}),
        ("state_update_to_dom", [update_ms / updates], {"updates": updates}),
        ("render_1000_rows", [large_list_ms], {"rows": 1000}),
        ("route_navigation", [navigation_ms], {}),
    ]:
        report.add(
            BenchmarkResult(
                name,
                parameters,
                observations,
                metrics,
                measurement_iterations=len(observations),
            )
        )
    report.write(performance_output / "browser.json")

    assert metrics["javascript_modules"] > 0
    assert metrics["javascript_gzip_bytes"] <= MAX_JAVASCRIPT_GZIP_BYTES, (
        f"shipped client bundle is {metrics['javascript_gzip_bytes']} gzip bytes, "
        f"over the {MAX_JAVASCRIPT_GZIP_BYTES} budget "
        "(override via REFLEX_PERFORMANCE_JS_GZIP_BUDGET)"
    )
    assert heap_after > 0


def _timed_through_paint(page: Page, action, expectation) -> float:
    """Time an interaction from click through the following paint.

    Args:
        page: Playwright browser page.
        action: Callable triggering the interaction.
        expectation: Callable asserting the resulting DOM change.

    Returns:
        Elapsed milliseconds including a double requestAnimationFrame flush.
    """
    started = time.perf_counter_ns()
    action()
    expectation()
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    return (time.perf_counter_ns() - started) / 1_000_000


@pytest.mark.performance
def test_browser_rows_report(
    performance_load_app: AppHarness,
    page: Page,
    performance_output: Path,
    performance_scale: str,
):
    """Measure keyed-list DOM operations: create, partial update, select, swap.

    The discriminating js-framework-benchmark operations for a keyed list
    rendered through ``rx.foreach``: full create, every-tenth-row update, a
    selection that must not re-render other rows, and a two-row swap that
    stresses keyed reconciliation. Durations include the following paint.

    Args:
        performance_load_app: Running production app.
        page: Playwright browser page.
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    assert performance_load_app.frontend_url is not None
    page.goto(performance_load_app.frontend_url.rstrip("/") + "/rows")
    expect(page.locator("#rows-hydrated")).to_have_text("hydrated")
    expect(page.locator("#selected-row")).to_have_text("-1")

    create_ms = _timed_through_paint(
        page,
        lambda: page.locator("#create-rows").click(),
        lambda: expect(page.locator(".row")).to_have_count(1000),
    )
    partial_ms = _timed_through_paint(
        page,
        lambda: page.locator("#partial-update").click(),
        lambda: expect(page.locator("#row-990")).to_have_text("row 990 !!!"),
    )
    select_ms = _timed_through_paint(
        page,
        lambda: page.locator("#row-500").click(),
        lambda: expect(page.locator("#selected-row")).to_have_text("500"),
    )
    swap_ms = _timed_through_paint(
        page,
        lambda: page.locator("#swap-rows").click(),
        lambda: expect(page.locator("#row-1")).to_have_text("row 998"),
    )

    report = PerformanceReport(
        "browser-rows",
        metadata={"scale": performance_scale, "rows": 1000},
    )
    for name, duration in [
        ("create_1000_rows", create_ms),
        ("partial_update_every_10th", partial_ms),
        ("select_row", select_ms),
        ("swap_rows", swap_ms),
    ]:
        report.add(
            BenchmarkResult(
                name,
                {"rows": 1000},
                [duration],
                {},
                measurement_iterations=1,
            )
        )
    report.write(performance_output / "browser-rows.json")
