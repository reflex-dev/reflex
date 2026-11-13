"""Run events.simple.* for real against the playground.

They compile and start the playground (bun, node and network needed), so they
only run when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/suites/test_events_app.py``. With
``REFLEX_BENCH_NETWORK_TESTS=1`` they also run against reflex 0.8.23 from PyPI.
"""

from __future__ import annotations

import multiprocessing
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
ECHO_KEY = (
    '"reflex___state____state.playground___state____bench_state":{"last_seq_rx_state_":'
)
# The board's parent states depend on the subject.
BOARD_KEY = '.playground___state____board_state":{'
SUBJECTS = [
    "workspace",
    pytest.param(
        "0.8.23",
        marks=pytest.mark.skipif(
            os.environ.get("REFLEX_BENCH_NETWORK_TESTS") != "1",
            reason="installs reflex 0.8.23 from PyPI; set REFLEX_BENCH_NETWORK_TESTS=1",
        ),
    ),
]


def _owned_processes() -> list[psutil.Process]:
    """Find processes started by any reflex-bench app driver.

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


@pytest.mark.parametrize("reflex", SUBJECTS)
def test_simple_events_for_real(
    reflex: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("REFLEX_BENCH_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CI", raising=False)
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        cli.cli,
        [
            "run", "events.simple.capacity", "events.simple.latency",
            "--reflex", reflex,
            "--param", "manager=memory", "--param", "sessions=1", "--param", "rate=20",
            "--runs", "1", "--no-save", "--json", str(out),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    entries = {
        (entry["id"], tuple(sorted(entry["params"].items()))): entry
        for entry in load(out)["benchmarks"]
    }
    assert set(entries) == {
        ("events.simple.capacity", (("manager", "memory"), ("sessions", 1))),
        (
            "events.simple.latency",
            (("manager", "memory"), ("rate", 20), ("sessions", 1)),
        ),
    }
    for entry in entries.values():
        assert entry["status"] == "ok", entry["error"]
        (extra,) = entry["sample_extra"]
        assert extra is not None
        assert extra["unanswered"] == 0
        assert extra["session_errors"] == []
        assert ECHO_KEY in extra["reply_frame"]
    latency = entries[
        "events.simple.latency", (("manager", "memory"), ("rate", 20), ("sessions", 1))
    ]
    assert latency["metrics"]["unanswered"]["samples"]["A"] == [0.0]
    (extra,) = latency["sample_extra"]
    assert extra is not None
    assert extra["offered_rate"] == pytest.approx(20.0)
    assert _owned_processes() == []
    # The generator processes are gone too.
    assert multiprocessing.active_children() == []


@pytest.mark.parametrize("reflex", SUBJECTS)
def test_shared_events_for_real(
    reflex: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("REFLEX_BENCH_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CI", raising=False)
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        cli.cli,
        [
            "run", "events.shared_fanout.broadcast", "events.shared_contention.capacity",
            "--reflex", reflex,
            "--param", "manager=memory", "--param", "linked=3", "--param", "sessions=3",
            "--runs", "1", "--no-save", "--json", str(out),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    entries = {entry["id"]: entry for entry in load(out)["benchmarks"]}
    assert set(entries) == {
        "events.shared_fanout.broadcast",
        "events.shared_contention.capacity",
    }
    for entry in entries.values():
        assert entry["status"] == "ok", entry["error"]
        (extra,) = entry["sample_extra"]
        assert extra is not None
        assert extra["session_errors"] == []
        assert extra["sessions"] == 3
        assert BOARD_KEY in extra["reply_frame"]
        assert '"last_client_rx_state_":' in extra["reply_frame"]
    fanout = entries["events.shared_fanout.broadcast"]
    (extra,) = fanout["sample_extra"]
    assert extra is not None
    assert extra["unanswered"] == 0
    assert extra["spread_s"]["max"] > 0
    assert fanout["metrics"]["broadcast_p50"]["samples"]["A"][0] > 0
    assert _owned_processes() == []
    assert multiprocessing.active_children() == []
