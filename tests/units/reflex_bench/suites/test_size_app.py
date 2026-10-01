"""Run size.export for real: export examples/playground with the workspace reflex.

It installs the frontend packages and builds the app (bun, node and network
needed), so it only runs when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/suites/test_size_app.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from reflex_bench import cli
from reflex_bench.schema import load, timed_values

pytestmark = pytest.mark.skipif(
    os.environ.get("REFLEX_BENCH_APP_TESTS") != "1",
    reason="exports a real reflex app; set REFLEX_BENCH_APP_TESTS=1",
)


def test_size_export_for_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REFLEX_BENCH_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CI", raising=False)
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        cli.cli, ["run", "size.*", "--no-save", "--json", str(out)]
    )
    assert result.exit_code == 0, result.output
    (entry,) = load(out)["benchmarks"]
    assert entry["status"] == "ok", entry["traceback_tail"]
    values = {name: timed_values(entry, name) for name in entry["metrics"]}
    assert all(len(samples) == 1 for samples in values.values())
    assert all(samples[0] > 0 for samples in values.values()), values
    assert values["initial_gzip"][0] < values["total_gzip"][0]
    (extra,) = entry["sample_extra"]
    assert extra is not None
    assert extra["initial_files"]
    assert extra["fixture_hash"].startswith("sha256:")
