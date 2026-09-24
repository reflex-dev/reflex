"""Tests for reflex_bench.suites.browser, with a fake app and browser."""

from __future__ import annotations

from pathlib import Path

import pytest
from reflex_bench import fixtures, registry
from reflex_bench.context import Context
from reflex_bench.registry import SampleResult
from reflex_bench.suites import browser as suite

from tests.units.reflex_bench.factories import make_context

from .fakes import FakeApp, FakeBrowser, FakeTab


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Context:
    """Swap in the fakes.

    Returns:
        The benchmark context.
    """
    monkeypatch.setattr(suite, "AppProcess", FakeApp)
    monkeypatch.setattr(suite, "Browser", FakeBrowser)
    monkeypatch.setattr(FakeBrowser, "configure", None)
    monkeypatch.setattr(FakeApp, "created", [])
    monkeypatch.setattr(FakeBrowser, "created", [])
    return make_context(tmp_path)


def test_registrations():
    found = registry.discover()
    expected = {
        "browser.dev.ready": (("pr", "daily"), None, "startup"),
        "browser.preview.ready": (("daily",), "0.9.8", "startup"),
        "browser.prod.ready": (("daily",), None, "startup"),
        "browser.prod.pageload": (("daily",), None, "latency"),
    }
    assert {id for id in found if id.startswith("browser.")} == set(expected)
    for id, (suites, min_version, kind) in expected.items():
        bench = found[id]
        assert (bench.suites, bench.min_version, bench.kind) == (
            suites,
            min_version,
            kind,
        )
    for id in ("browser.dev.ready", "browser.preview.ready", "browser.prod.ready"):
        # The first start of a run is much slower than the rest.
        assert found[id].warmup == 1
    ready = found["browser.dev.ready"]
    assert list(ready.metrics) == [
        "process_ready",
        "http_ready",
        "interactive_ready",
        "nav_to_interactive",
        "fcp",
    ]
    assert {metric.unit for metric in ready.metrics.values()} == {"s"}
    pageload = found["browser.prod.pageload"]
    assert pageload.params == {"cpu": (1, 4)}
    assert pageload.warmup == 1
    assert {name: metric.unit for name, metric in pageload.metrics.items()} == {
        "fcp": "s",
        "lcp": "s",
        "interactive": "s",
        "tbt": "s",
        "ws_bytes": "B",
        "transfer_bytes": "B",
    }
    # The same page transfers the same bytes in every sample.
    assert {
        name for name, metric in pageload.metrics.items() if metric.assume == "exact"
    } == {
        "ws_bytes",
        "transfer_bytes",
    }


@pytest.mark.parametrize(
    ("cls", "mode"),
    [
        (suite.DevReady, "dev"),
        (suite.PreviewReady, "preview"),
        (suite.ProdReady, "prod"),
    ],
)
def test_ready_measures_the_three_tiers_in_order(
    ctx: Context, cls: type[suite.DevReady], mode: str
):
    bench = cls()
    bench.setup(ctx)
    result = bench.sample(ctx)
    app = FakeApp.created[0]
    assert app.mode == mode
    assert app.app_dir == fixtures.app_dir(ctx)
    assert app.env == fixtures.app_env(ctx, fixtures.app_dir(ctx))
    assert app.calls == ["start", "http", "interactive /"]
    assert isinstance(result, SampleResult)
    assert result.values == {
        "process_ready": 1.5,
        "http_ready": 2.0,
        "interactive_ready": 3.0,
        "nav_to_interactive": 0.8,
        "fcp": 2.5,
    }
    extra = result.extra
    assert extra is not None
    assert extra["gaps"] == {
        "http_after_process_s": 0.5,
        "interactive_after_http_s": 1.0,
    }
    assert extra["fixture_hash"] == fixtures.fixture_hash("playground")
    assert extra["lcp_s"] == pytest.approx(2.6)
    assert extra["console"] == {"warning": 1}
    tab = FakeBrowser.created[0].tabs[0]
    bench.conclude(ctx)
    assert tab.closed
    assert app.calls[-1] == "stop"
    bench.cleanup(ctx)
    assert FakeBrowser.created[0].closed


def test_ready_conclude_stops_the_app_after_a_failed_sample(
    ctx: Context, monkeypatch: pytest.MonkeyPatch
):
    def fail(self: FakeBrowser, app: FakeApp, path: str = "/") -> None:
        msg = "never hydrated"
        raise TimeoutError(msg)

    monkeypatch.setattr(FakeBrowser, "interactive", fail)
    bench = suite.DevReady()
    bench.setup(ctx)
    with pytest.raises(TimeoutError):
        bench.sample(ctx)
    bench.conclude(ctx)
    assert FakeApp.created[0].calls[-1] == "stop"
    bench.conclude(ctx)  # nothing left to stop
    assert FakeApp.created[0].calls.count("stop") == 1


def test_ready_conclude_on_a_foreign_thread_kills_the_browser(ctx: Context):
    bench = suite.DevReady()
    bench.setup(ctx)
    bench.sample(ctx)
    browser = FakeBrowser.created[0]
    browser.owner = False
    bench.conclude(ctx)
    assert browser.killed
    assert FakeApp.created[0].calls[-1] == "stop"


def test_total_blocking_time_counts_long_tasks_before_interactive():
    tasks = [
        {"start": 10.0, "duration": 120.0},  # 70 ms over the 50 ms budget
        {"start": 200.0, "duration": 40.0},  # not a blocking task
        {"start": 300.0, "duration": 80.0},  # 30 ms
        {"start": 900.0, "duration": 500.0},  # after interactive
    ]
    assert suite.total_blocking_time(tasks, interactive_ms=800.0) == pytest.approx(0.1)
    assert suite.total_blocking_time([], interactive_ms=800.0) == pytest.approx(0)


class _PageloadTab(FakeTab):
    """A page with paint timings, long tasks and traffic."""

    ws_bytes = 1234
    transfer_bytes = 98_765

    def timings(self) -> dict[str, object]:
        self.calls.append(("timings",))
        return {
            "fcp": 500.0,
            "lcp": 650.0,
            "longtasks": [{"start": 100.0, "duration": 90.0}],
            "loafs": [],
        }


def test_pageload(ctx: Context, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(FakeBrowser, "tab_class", _PageloadTab)
    ctx.params = {"cpu": 4}
    bench = suite.ProdPageload()
    bench.setup(ctx)
    app = FakeApp.created[0]
    browser = FakeBrowser.created[0]
    assert app.mode == "prod"
    assert app.calls == ["start", "http"]
    assert browser.cpu_throttle == 4
    result = bench.sample(ctx)
    assert isinstance(result, SampleResult)
    assert result.values == {
        "fcp": 0.5,
        "lcp": 0.65,
        "interactive": 0.8,
        "tbt": pytest.approx(0.04),
        "ws_bytes": 1234,
        "transfer_bytes": 98_765,
    }
    tab = browser.tabs[0]
    # The sample ends with the page's own timings: nothing waits after interactive.
    assert tab.calls == [("timings",)]
    assert result.extra is not None
    assert result.extra["cpu"] == 4
    assert result.extra["fixture_hash"] == fixtures.fixture_hash("playground")
    bench.conclude(ctx)
    assert tab.closed
    assert app.calls[-1] != "stop"  # one server for the whole instance
    bench.cleanup(ctx)
    assert browser.closed
    assert app.calls[-1] == "stop"
