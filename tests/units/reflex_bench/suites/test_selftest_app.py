"""Run the selftest.app.* benchmarks for real against the workspace reflex.

They init, compile and start a real blank app (bun, node and network needed),
so they only run when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/suites/test_selftest_app.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import psutil
import pytest
from click.testing import CliRunner
from reflex_bench import cli
from reflex_bench.drivers.app_process import OWNER_ENV
from reflex_bench.schema import load

pytestmark = pytest.mark.skipif(
    os.environ.get("REFLEX_BENCH_APP_TESTS") != "1",
    reason="starts real reflex apps; set REFLEX_BENCH_APP_TESTS=1",
)


def _owned_processes() -> list[psutil.Process]:
    """Find processes started by any reflex-bench driver.

    Returns:
        The processes carrying the driver's owner token.
    """
    owned = []
    for proc in psutil.process_iter():
        try:
            if OWNER_ENV in proc.environ():
                owned.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return owned


def test_app_self_tests_for_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REFLEX_BENCH_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CI", raising=False)
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        cli.cli,
        ["run", "selftest.app.*", "--runs", "3", "--no-save", "--json", str(out)],
    )
    assert result.exit_code == 0, result.output
    entries = {entry["id"]: entry for entry in load(out)["benchmarks"]}
    assert {entry["status"] for entry in entries.values()} == {"ok"}, result.output

    compile_entry = entries["selftest.app.compile"]
    assert len(compile_entry["metrics"]["peak_mem"]["samples"]["A"]) == 3
    assert min(compile_entry["metrics"]["peak_mem"]["samples"]["A"]) > 50 * 1024**2
    for extra in compile_entry["sample_extra"]:
        assert extra is not None
        assert extra["memory_method"] in {"cgroup", "pss_sampling"}
        assert extra["phases"]["mismatch"] is False
        assert extra["phases"]["python"] > 0

    ready = entries["selftest.app.dev_ready"]["metrics"]
    for process_ready, http_ready in zip(
        ready["process_ready"]["samples"]["A"],
        ready["http_ready"]["samples"]["A"],
        strict=True,
    ):
        assert 0 < process_ready <= http_ready
    assert _owned_processes() == []
