"""Run the wire benchmarks for real against the playground and the generated wire_delta app.

They compile and start reflex apps (bun, node and network needed), so they
only run when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/suites/test_wire_app.py``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from reflex_bench import cli
from reflex_bench.drivers.events import ROOT_STATE
from reflex_bench.schema import load
from reflex_bench.suites import wire

pytestmark = pytest.mark.skipif(
    os.environ.get("REFLEX_BENCH_APP_TESTS") != "1",
    reason="starts real reflex apps; set REFLEX_BENCH_APP_TESTS=1",
)
COLLECTION_VAR = {
    "append_item": "items_rx_state_",
    "set_one_item": "items_rx_state_",
    "set_dict_key": "table_rx_state_",
    "update_row_field": "rows_rx_state_",
}


def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *filters: str) -> list[Any]:
    """Run reflex-bench once and read the result.

    Args:
        tmp_path: The test's directory; the bench home is below it.
        monkeypatch: Sets the bench home.
        *filters: The benchmark globs.

    Returns:
        The benchmark entries.
    """
    monkeypatch.setenv("REFLEX_BENCH_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CI", raising=False)
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        cli.cli, ["run", *filters, "--runs", "1", "--no-save", "--json", str(out)]
    )
    assert result.exit_code == 0, result.output
    return [dict(entry) for entry in load(out)["benchmarks"]]


def test_navigate_for_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    entries = {
        entry["params"]["route"]: entry
        for entry in run(tmp_path, monkeypatch, "wire.navigate")
    }
    assert set(entries) == set(wire.ROUTES)
    for route, entry in entries.items():
        assert entry["status"] == "ok", entry["error"]
        (extra,) = entry["sample_extra"]
        assert extra["response_frames"] == 1
        # The reply carries the root state's router, set to the new route.
        pathname = wire.ROUTES[route][0]
        assert f'"path":"{pathname}"' in extra["reply"]
        assert set(extra["delta_bytes"]) == {ROOT_STATE}
        # The hydration on "/" came first.
        assert extra["hydration"]["received_frames"] == 4
    # The dynamic route argument is a var of the root state.
    assert '"item_id_rx_state_":"42"' in entries["item"]["sample_extra"][0]["reply"]


def test_delta_for_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    entries = {
        entry["params"]["change"]: entry
        for entry in run(tmp_path, monkeypatch, "wire.delta")
    }
    assert set(entries) == set(wire.CHANGES)
    replies = {}
    for change, entry in entries.items():
        assert entry["status"] == "ok", entry["error"]
        (extra,) = entry["sample_extra"]
        assert extra["response_frames"] == 1
        assert set(extra["delta_bytes"]) == {wire.WIRE_STATE}
        replies[change] = extra["reply"]
    # Each change's reply carries its collection; the control's carries none.
    for change, var in COLLECTION_VAR.items():
        assert var in replies[change], change
    assert not any(var in replies["set_scalar"] for var in COLLECTION_VAR.values())
    assert '"scalar_rx_state_":1' in replies["set_scalar"]
