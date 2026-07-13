"""Production browser, bundle, hydration, and DOM-update benchmarks."""

from __future__ import annotations

import gzip
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd
from tests.benchmarks.support import BenchmarkResult, PerformanceReport
from tests.benchmarks.support.apps import load_app_source

MAX_JAVASCRIPT_GZIP_BYTES = 14_000_000


@pytest.fixture(scope="module")
def performance_browser_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Build and serve the representative application in production mode.

    Args:
        tmp_path_factory: Pytest temporary directory factory.

    Yields:
        Running production app harness.
    """
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("performance_browser"),
        app_source=load_app_source(),
        app_name="performance_browser",
    ) as harness:
        yield harness


def _bundle_metrics(root: Path) -> dict[str, int]:
    """Calculate bundle module and compressed-size metrics.

    Args:
        root: Reflex application root.

    Returns:
        JavaScript module, raw byte, and gzip byte counts.
    """
    files = [
        path
        for path in (root / ".web").rglob("*")
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
    performance_browser_app: AppHarness,
    page: Page,
    performance_output: Path,
    performance_scale: str,
):
    """Measure hydration, state-to-DOM updates, large lists, navigation, and heap.

    Args:
        performance_browser_app: Running production app.
        page: Playwright browser page.
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    assert performance_browser_app.frontend_url is not None
    page.add_init_script(
        """
        window.__reflexLongTasks = [];
        new PerformanceObserver((list) => {
          window.__reflexLongTasks.push(...list.getEntries().map((entry) => entry.duration));
        }).observe({entryTypes: ['longtask']});
        """
    )
    started = time.perf_counter_ns()
    page.goto(performance_browser_app.frontend_url)
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
        _bundle_metrics(performance_browser_app.app_path)
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
    assert metrics["javascript_gzip_bytes"] <= MAX_JAVASCRIPT_GZIP_BYTES
    assert heap_after > 0
