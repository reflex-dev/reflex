"""Run browser.dev.ready and hmr.render.leaf for real against the workspace reflex.

They stage and compile the playground, start real dev apps and drive headless
Chromium (bun, network and ``uv run playwright install --only-shell chromium``
needed), so they only run when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/suites/test_browser_hmr_app.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import psutil
import pytest
from click.testing import CliRunner
from reflex_bench import cli, machine
from reflex_bench.drivers.app_process import OWNER_ENV
from reflex_bench.schema import ResultDoc, load

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("REFLEX_BENCH_APP_TESTS") != "1",
        reason="starts real reflex apps and a browser; set REFLEX_BENCH_APP_TESTS=1",
    ),
    pytest.mark.skipif(
        not machine._playwright_chromium(), reason="no Playwright chromium"
    ),
]


def _leftovers() -> list[psutil.Process]:
    """Find processes the drivers started: owned app and browser trees, Playwright drivers.

    Returns:
        The processes carrying an owner token, and Playwright driver children of
        the harness.
    """
    found = []
    for proc in psutil.process_iter():
        try:
            if OWNER_ENV in proc.environ():
                found.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for proc in psutil.Process().children(recursive=True):
        try:
            if "run-driver" in proc.cmdline() and proc.status() != psutil.STATUS_ZOMBIE:
                found.append(proc)
        except psutil.NoSuchProcess:
            continue
    return found


def run_and_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    """Run browser.dev.ready and hmr.render.leaf through the CLI and check the results.

    Args:
        tmp_path: A scratch directory for the bench home and the result.
        monkeypatch: The pytest monkeypatch fixture.
        *args: More ``run`` arguments, e.g. ``--reflex 0.8.23``.
    """
    monkeypatch.setenv("REFLEX_BENCH_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CI", raising=False)
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        cli.cli,
        [
            "run",
            "browser.dev.ready",
            "hmr.render.leaf",
            "--runs",
            "2",
            "--warmup",
            "1",
            "--no-save",
            "--json",
            str(out),
            *args,
        ],
    )
    assert result.exit_code == 0, result.output
    doc: ResultDoc = load(out)
    entries = {entry["id"]: entry for entry in doc["benchmarks"]}
    assert {entry["status"] for entry in entries.values()} == {"ok"}, result.output

    ready = entries["browser.dev.ready"]["metrics"]
    tiers = zip(
        ready["process_ready"]["samples"]["A"],
        ready["http_ready"]["samples"]["A"],
        ready["interactive_ready"]["samples"]["A"],
        strict=True,
    )
    for process_ready, http_ready, interactive_ready in tiers:
        assert 0 < process_ready <= http_ready < interactive_ready

    leaf = entries["hmr.render.leaf"]
    latencies = leaf["metrics"]["latency"]["samples"]["A"]
    assert len(latencies) == 3  # one warmup and two timed edits
    assert all(0 < latency < 60 for latency in latencies)
    assert set(leaf["metrics"]["full_reloads"]["samples"]["A"]) == {0}
    extra = leaf["sample_extra"][-1]
    assert extra is not None
    hops = extra["hops"]
    assert 0 < hops["watcher_seen_s"] < hops["compile_done_s"] < hops["dom_updated_s"]
    assert _leftovers() == []


def test_browser_and_hot_reload_for_real(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    run_and_check(tmp_path, monkeypatch)
