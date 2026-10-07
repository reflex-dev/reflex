"""Run the memory benchmarks for real against the playground and the workspace reflex.

They compile and start the playground (bun, node and network needed), so they
only run when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/suites/test_memory_app.py``.
"""

from __future__ import annotations

import multiprocessing
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import psutil
import pytest
from click.testing import CliRunner
from reflex_bench import cli
from reflex_bench.collectors.cgroup import CgroupScope
from reflex_bench.drivers.app_process import OWNER_ENV
from reflex_bench.schema import load
from reflex_bench.store import HOME_ENV
from reflex_bench.suites import events as events_suite
from reflex_bench.suites.events import copy_tracked

pytestmark = pytest.mark.skipif(
    os.environ.get("REFLEX_BENCH_APP_TESTS") != "1",
    reason="starts real reflex apps; set REFLEX_BENCH_APP_TESTS=1",
)
# Inserted into BenchState. "x" * 4096 alone would be folded into one constant
# string by the compiler, so every event appends a new one.
LEAK_HANDLER = '''
    @rx.event
    def leak_seq(self, seq: int):
        """Keep 4 KiB per event forever: the deliberate leak of the memory tests.

        Args:
            seq: The sequence number the benchmark sent.
        """
        LEAKED.append("x" * 4096 + str(seq))
        self.last_seq = seq

'''


def run(tmp_path: Path, *args: str) -> list[dict[str, Any]]:
    """Run reflex-bench once and read the result.

    Args:
        tmp_path: The test's directory; the bench home is below it.
        *args: The ``run`` arguments.

    Returns:
        The benchmark entries.
    """
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        cli.cli, ["run", *args, "--no-save", "--json", str(out)]
    )
    assert out.exists(), result.output
    return [dict(entry) for entry in load(out)["benchmarks"]]


def assert_nothing_left(home: Path) -> None:
    """Check that no app process of this run and no scope unit is left.

    Args:
        home: This run's bench home; the apps it started carry it in their
            environment next to the owner token, other runs' apps do not.
    """
    left = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            environ = proc.environ()
            if OWNER_ENV in environ and environ.get(HOME_ENV) == str(home):
                left.append(f"{proc.pid}: {' '.join(proc.info['cmdline'] or ())}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    assert left == []
    # Generator, hold and echo processes are spawned children of this process.
    assert multiprocessing.active_children() == []
    if shutil.which("systemctl") is None:
        return
    units = subprocess.run(
        ["systemctl", "--user", "list-units", "reflex-bench-*", "--no-legend"],
        capture_output=True,
        text=True,
        check=False,
    )
    if units.returncode == 0:
        assert units.stdout.strip() == ""


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use a fresh bench home.

    Args:
        tmp_path: The test's directory.
        monkeypatch: Sets the environment.

    Returns:
        The bench home.
    """
    monkeypatch.setenv("REFLEX_BENCH_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CI", raising=False)
    return tmp_path / "home"


def test_each_memory_benchmark_once(tmp_path: Path, home: Path):
    ids = ["memory.compile.peak", "memory.idle", "memory.per_session", "memory.leak"]
    entries = run(
        tmp_path,
        *ids,
        "--runs", "1",
        "--param", "command=compile",
        "--param", "manager=memory",
        "--param", "max_sessions=50",
        "--param", "expiry_s=40",
        "--param", "events=3000",
    )  # fmt: skip
    found = {entry["id"]: entry for entry in entries}
    assert set(found) == set(ids)
    for bench_id, entry in found.items():
        assert entry["status"] == "ok", (bench_id, entry["error"])
        method = entry["dims"]["memory_method"]
        assert method in {"cgroup", "pss_sampling"}
        for extra in entry["sample_extra"]:
            assert extra["memory_method"] == method
    levels = found["memory.per_session"]["sample_extra"][0]["levels"]
    assert [level["sessions"] for level in levels] == [0, 25, 50]
    assert found["memory.idle"]["metrics"]["pss"]["samples"]["A"][0] > 50 * 1024**2
    assert_nothing_left(home)


def test_the_512mb_gate(tmp_path: Path, home: Path):
    if (reason := CgroupScope.available()) is not None:
        pytest.skip(f"memory.boot_512mb needs cgroup scopes: {reason}")
    (entry,) = run(
        tmp_path, "memory.boot_512mb", "--runs", "1", "--param", "manager=memory"
    )
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"memory_method": "cgroup", "fixture": "playground"}
    assert entry["metrics"]["passed"]["samples"]["A"] == [1.0]
    (extra,) = entry["sample_extra"]
    for phase in ("compile", "boot", "serve"):
        assert extra["phases"][phase]["oom_kill"] == 0
        assert 0 < extra["phases"][phase]["memory_peak_bytes"] <= 512 * 1024**2
    assert_nothing_left(home)


def test_a_deliberate_leak_fails_and_the_playground_passes(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
):
    leaky = tmp_path / "leaky"
    copy_tracked(events_suite.PLAYGROUND, leaky)
    state = leaky / "playground" / "state.py"
    source = state.read_text(encoding="utf-8")
    marker = "    @rx.event\n    def bench_value(self):"
    assert marker in source
    source = source.replace(
        "\n\nclass PlaygroundState",
        "\n\nLEAKED: list[str] = []\n\n\nclass PlaygroundState",
        1,
    )
    state.write_text(
        source.replace(marker, LEAK_HANDLER.lstrip("\n") + marker, 1), encoding="utf-8"
    )

    def copy_leaky(source: Path, target: Path) -> None:
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(leaky, target)

    with monkeypatch.context() as patch:
        patch.setattr(events_suite, "copy_tracked", copy_leaky)
        (leak,) = run(
            tmp_path,
            "memory.leak",
            "--runs", "1",
            "--param", "manager=memory",
            "--param", "event=leak_seq",
            "--param", "events=3000",
        )  # fmt: skip
    assert leak["status"] == "failed"
    assert leak["error"].startswith("LeakDetected: memory grows by ")
    assert_nothing_left(home)

    (plain,) = run(
        tmp_path,
        "memory.leak",
        "--runs", "3",
        "--param", "manager=memory",
        "--param", "events=3000",
    )  # fmt: skip
    assert plain["status"] == "ok", plain["error"]
    assert plain["metrics"]["passed"]["samples"]["A"] == [1.0, 1.0, 1.0]
    assert_nothing_left(home)
