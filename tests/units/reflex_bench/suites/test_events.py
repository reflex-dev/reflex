"""Tests for reflex_bench.suites.events.

Nothing here starts a reflex app: the app and load hooks are replaced where a
test runs a benchmark through the scheduler. ``test_events_app.py`` runs them
for real.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import psutil
import pytest
from reflex_bench import cli, registry
from reflex_bench.drivers.events import LoadResult, Mode
from reflex_bench.scheduler import Planned, Policy, Scheduler, plan
from reflex_bench.suites import events as suite

from tests.units.reflex_bench.factories import make_load_result, make_subject

SHAPES = ("background", "complex", "cross", "simple")
CHEAP = [
    "events.simple.capacity[manager=memory,sessions=10]",
    "events.simple.latency[manager=memory,sessions=10,rate=500]",
]


def selected(suite_name: str | None, *filters: str) -> list[Planned]:
    chosen = registry.select(registry.discover().values(), filters, suite_name)
    return plan(chosen, suite=suite_name)


def names(suite_name: str | None, *filters: str) -> list[str]:
    return [planned.name for planned in selected(suite_name, *filters)]


def test_instance_ids_and_params():
    everything = names(None, "events.*")
    assert suite.MANAGERS[:2] == ("memory", "disk")
    # Capacity and latency per shape, one knee (simple) and the 1 Hz sessions.
    assert len(everything) == len(suite.MANAGERS) * (4 * (4 + 4) + 4 + 3)
    assert "events.simple.capacity[manager=memory,sessions=1]" in everything
    assert "events.simple.capacity[manager=disk,sessions=200]" in everything
    assert "events.cross.latency[manager=memory,sessions=10,rate=auto]" in everything
    assert "events.simple.knee[manager=disk,sessions=50]" in everything
    assert "events.sessions.at_1hz[manager=memory,sessions=1000]" in everything
    assert not [name for name in everything if name.startswith("events.cross.knee")]


def test_smoke_and_daily_run_two_cheap_points():
    assert names("smoke", "events.*") == CHEAP
    assert names("daily", "events.*") == CHEAP


def test_daily_events_fit_the_ci_budget():
    # The estimate `list` shows with the default policy (10 runs at least).
    total = sum(cli._estimate(p.benchmark, Policy()) for p in selected("daily"))
    assert total <= 3 * 60


def test_suites():
    found = registry.discover()
    assert found["events.simple.capacity"].suites == ("smoke", "daily")
    assert found["events.simple.latency"].suites == ("smoke", "daily")
    # Everything else only runs with --suite all or by name.
    for shape in set(SHAPES) - {"simple"}:
        assert found[f"events.{shape}.capacity"].suites == ()
        assert found[f"events.{shape}.latency"].suites == ()
    assert found["events.simple.knee"].suites == ()
    assert found["events.sessions.at_1hz"].suites == ()
    assert found["selftest.events.calibrate"].suites == ("selftest",)
    assert "events.sessions.at_1hz[manager=memory,sessions=50]" in names("all")
    assert "events.simple.knee[manager=memory,sessions=10]" in names("all")
    assert "events.complex.capacity[manager=disk,sessions=200]" in names("all")


def test_redis_is_measured_only_with_a_redis_url():
    assert suite.managers({}) == ("memory", "disk")
    assert suite.managers({"REFLEX_REDIS_URL": ""}) == ("memory", "disk")
    assert suite.managers({"REFLEX_REDIS_URL": "redis://localhost:6379"}) == (
        "memory",
        "disk",
        "redis",
    )
    assert registry.discover()["events.simple.capacity"].params["manager"] == (
        suite.MANAGERS
    )


def test_the_shapes_are_the_playground_handlers():
    state = "reflex___state____state.playground___state____bench_state"
    assert {name: shape.name for name, shape in suite.SHAPES.items()} == {
        "simple": f"{state}.set_seq",
        "complex": f"{state}.set_seq_complex",
        "cross": f"{state}.set_seq_cross",
        "background": f"{state}.set_seq_background",
    }
    for shape in suite.SHAPES.values():
        assert (shape.delta_key, shape.seq_var) == (state, "last_seq_rx_state_")
        assert shape.payload(7) == {"seq": 7}
    # Background tasks may finish in any order; the others answer in order.
    assert [name for name, shape in suite.SHAPES.items() if not shape.ordered] == [
        "background"
    ]


def test_server_env(tmp_path: Path):
    base = {"PATH": "/venv/bin", "REFLEX_REDIS_URL": "redis://localhost:6379"}
    env = suite.server_env(base, "memory", tmp_path / "states")
    assert env["REFLEX_STATE_MANAGER_MODE"] == "memory"
    # One worker whatever the manager: reflex picks more when redis is configured.
    assert env["GRANIAN_WORKERS"] == "1"
    assert env["REFLEX_STATES_WORKDIR"] == str(tmp_path / "states")
    assert env["PATH"] == "/venv/bin"
    # With a redis URL reflex would use redis whatever the mode says.
    assert "REFLEX_REDIS_URL" not in env
    redis = suite.server_env(base, "redis", tmp_path / "states")
    assert redis["REFLEX_STATE_MANAGER_MODE"] == "redis"
    assert redis["REFLEX_REDIS_URL"] == "redis://localhost:6379"
    assert "REFLEX_REDIS_URL" not in suite.server_env({}, "disk", tmp_path)


@pytest.mark.parametrize(
    ("allowed", "expected"),
    [
        ([0, 1, 2, 3], {"server": [1], "generator": [2, 3]}),
        (range(8), {"server": [1, 2, 3], "generator": [4, 5, 6, 7]}),
        ([4, 5, 6, 7], {"server": [4, 5], "generator": [6, 7]}),
        ([3, 1, 2, 0, 4], {"server": [1], "generator": [2, 3, 4]}),
        ([0, 1, 2], None),
    ],
)
def test_split_cpus(allowed, expected):
    assert suite.split_cpus(allowed) == expected


def test_generator_processes():
    assert suite.generator_processes(10, [2, 3]) == 1
    assert suite.generator_processes(50, [2, 3]) == 2
    assert suite.generator_processes(200, list(range(8, 16))) == 4
    assert suite.generator_processes(11, [5]) == 1
    assert suite.generator_processes(1000, None) >= 1


def step(offered: float, achieved: float, p99: float | None, unanswered: int = 0):
    return {
        "offered": offered,
        "achieved": achieved,
        "p99": p99,
        "unanswered": unanswered,
    }


def test_knee_is_the_highest_step_that_keeps_up():
    steps = [
        step(100, 100, 0.002),
        step(500, 500, 0.003),
        # Keeps up but the tail is past 3x the low-load p99.
        step(800, 800, 0.0061),
        step(900, 895, 0.005),
        # Under 99 % of the offered rate.
        step(1000, 985, 0.004),
        # An unanswered event disqualifies a step.
        step(1100, 1100, 0.005, unanswered=1),
    ]
    assert suite.find_knee(steps) == (900, 0.002)


def test_no_knee_when_no_step_qualifies():
    steps = [step(100, 90, 0.002), step(200, 150, 0.01)]
    assert suite.find_knee(steps) == (0.0, 0.002)


def test_no_knee_without_a_low_load_measurement():
    with pytest.raises(ValueError, match="low-load step"):
        suite.find_knee([step(100, 0, None), step(200, 200, 0.01)])


def test_cpu_per_event():
    # 2.4 CPU seconds over 12 000 answered events is 200 μs each.
    assert suite.cpu_per_event(2.4, 12_000) == pytest.approx(200e-6)
    with pytest.raises(ValueError, match="no answered event"):
        suite.cpu_per_event(1.0, 0)
    with pytest.raises(ValueError, match="went back"):
        suite.cpu_per_event(-0.2, 12_000)


class FakeProcess:
    """A process whose CPU times are given, or that is gone."""

    def __init__(self, own: float = 0.0, reaped: float = 0.0, gone: bool = False):
        """Set the CPU seconds.

        Args:
            own: Its own user and system time.
            reaped: The time of the children it reaped.
            gone: Whether it exited.
        """
        self.own, self.reaped, self.gone = own, reaped, gone

    def cpu_times(self) -> SimpleNamespace:
        """Report the CPU times, split evenly between user and system.

        Returns:
            The times.

        Raises:
            psutil.NoSuchProcess: When the process is gone.
        """
        if self.gone:
            raise psutil.NoSuchProcess(1)
        return SimpleNamespace(
            user=self.own / 2,
            system=self.own / 2,
            children_user=self.reaped / 2,
            children_system=self.reaped / 2,
        )


def tree_cpu(*processes: FakeProcess) -> float:
    return suite.tree_cpu_s(cast("list[psutil.Process]", list(processes)))


def test_tree_cpu_keeps_the_time_of_a_process_that_exits():
    # A worker at 5 s uses 1 s more, exits, and granian reaps it (0.5 s itself).
    start = tree_cpu(FakeProcess(own=3.0), FakeProcess(own=5.0))
    end = tree_cpu(FakeProcess(own=3.5, reaped=6.0), FakeProcess(gone=True))
    assert end - start == pytest.approx(1.5)


def test_copy_tracked_files_leaves_out_build_output(tmp_path: Path):
    source = tmp_path / "source"
    (source / "pkg").mkdir(parents=True)
    (source / "pkg" / "app.py").write_text("tracked\n", encoding="utf-8")
    (source / ".gitignore").write_text(".web/\n", encoding="utf-8")
    (source / ".web").mkdir()
    (source / ".web" / "built.js").write_text("ignored\n", encoding="utf-8")
    (source / "notes.txt").write_text("untracked\n", encoding="utf-8")

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
            cwd=source,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    git("add", "pkg/app.py", ".gitignore")
    git("commit", "-q", "-m", "init")
    target = tmp_path / "target"
    suite.copy_tracked(source, target)
    copied = sorted(
        str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()
    )
    assert copied == [".gitignore", "pkg/app.py"]


CLOSED = make_load_result(
    mode="closed",
    offered_rate=None,
    response_s=None,
    lag_s=None,
    answered=12_000,
    answered_rate=1200.0,
)


STALLED = make_load_result(lag_s={"p50": 1.5e-4, "p99": 0.0287, "max": 0.078})


def run_instance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bench_id: str,
    params: dict[str, str],
    results: dict[Mode, LoadResult | list[LoadResult]],
    runs: int = 1,
) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    """Run one instance through the scheduler with the backend replaced.

    Args:
        tmp_path: The bench home.
        monkeypatch: Replaces the app, the backend and the loads.
        bench_id: The benchmark.
        params: Its parameter values.
        results: What a load returns, per mode; a list is returned in order.
        runs: The timed runs.

    Returns:
        The result entry and the backend calls in order.
    """
    calls: list[tuple[Any, ...]] = []

    def run(self: Any, mode: Mode, rate: float | None, window: suite.Window):
        calls.append(("run", mode, rate, window))
        canned = results[mode]
        return (canned.pop(0) if isinstance(canned, list) else canned), 1.2

    monkeypatch.setattr(suite, "prepare_app", lambda ctx: None)
    monkeypatch.setattr(
        suite._Backend, "start_app", lambda self: calls.append(("app",))
    )
    monkeypatch.setattr(suite._Backend, "run", run)
    monkeypatch.setattr(
        suite._Backend, "stop_load", lambda self: calls.append(("stop_load",))
    )
    monkeypatch.setattr(suite._Backend, "stop", lambda self: calls.append(("stop",)))
    bench = registry.discover()[bench_id]
    (param_set,) = bench.expand(params)
    runner = Scheduler(make_subject(), Policy(runs=runs), home=tmp_path, seed=1)
    return dict(runner.run_one(Planned(bench, param_set))), calls


def run_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: LoadResult
) -> dict[str, Any]:
    """Run events.simple.capacity once with a canned load result.

    Args:
        tmp_path: The bench home.
        monkeypatch: Replaces the app and the load.
        result: What the load returns.

    Returns:
        The result entry.
    """
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.capacity",
        {"manager": "memory", "sessions": "10"},
        {"closed": result},
    )
    # cleanup stops what setup started, also after a failed sample.
    assert calls[0] == ("app",)
    assert calls[-1] == ("stop",)
    return entry


def test_one_backend_serves_every_sample_of_an_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.capacity",
        {"manager": "memory", "sessions": "10"},
        {"closed": CLOSED},
        runs=3,
    )
    assert entry["status"] == "ok", entry["error"]
    # setup warms the backend with the probe, so no sample meets it cold.
    probe = ("run", "closed", None, suite.PROBE_WINDOW)
    load = ("run", "closed", None, suite.CAPACITY_WINDOW)
    # conclude stops a load a timed-out sample left running; cleanup the backend.
    assert calls == [("app",), probe, *[load, ("stop_load",)] * 3, ("stop",)]
    assert suite.CAPACITY_WINDOW == (1.0, 3.0)


def test_latency_probes_the_capacity_once_per_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.latency",
        {"manager": "memory", "sessions": "10", "rate": "auto"},
        {"closed": CLOSED, "open": make_load_result()},
        runs=2,
    )
    assert entry["status"] == "ok", entry["error"]
    probe = ("run", "closed", None, suite.PROBE_WINDOW)
    # Half of the probed 1200 events per second.
    load = ("run", "open", 600.0, suite.LATENCY_WINDOW)
    assert calls == [("app",), probe, *[load, ("stop_load",)] * 2, ("stop",)]
    assert [extra["probed_capacity"] for extra in entry["sample_extra"]] == [
        1200.0,
        1200.0,
    ]


def test_latency_at_a_fixed_rate_still_warms_the_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.latency",
        {"manager": "memory", "sessions": "10", "rate": "500"},
        {"closed": CLOSED, "open": make_load_result()},
    )
    assert entry["status"] == "ok", entry["error"]
    probe = ("run", "closed", None, suite.PROBE_WINDOW)
    load = ("run", "open", 500.0, suite.LATENCY_WINDOW)
    assert calls == [("app",), probe, load, ("stop_load",), ("stop",)]
    assert entry["metrics"]["response_p99"]["samples"]["A"] == [0.0119]
    assert entry["metrics"]["unanswered"]["samples"]["A"] == [0.0]


def test_a_load_the_self_check_rejects_is_retaken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # A host stall of the generator's CPU fails the lag check of one load.
    reason = STALLED.check()
    assert reason is not None
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.latency",
        {"manager": "memory", "sessions": "10", "rate": "500"},
        {"closed": CLOSED, "open": [STALLED, make_load_result()]},
    )
    assert entry["status"] == "ok", entry["error"]
    probe = ("run", "closed", None, suite.PROBE_WINDOW)
    load = ("run", "open", 500.0, suite.LATENCY_WINDOW)
    assert calls == [("app",), probe, load, load, ("stop_load",), ("stop",)]
    assert entry["metrics"]["response_p99"]["samples"]["A"] == [0.0119]
    (extra,) = entry["sample_extra"]
    assert extra["rejected"] == [reason]


def test_a_load_that_fails_the_self_check_every_time_fails_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.latency",
        {"manager": "memory", "sessions": "10", "rate": "500"},
        {"closed": CLOSED, "open": STALLED},
    )
    assert entry["status"] == "failed"
    assert entry["error"].startswith(
        "GeneratorSaturated: generator saturated: send lag"
    )
    probe = ("run", "closed", None, suite.PROBE_WINDOW)
    load = ("run", "open", 500.0, suite.LATENCY_WINDOW)
    retakes = [load] * (1 + suite.RETAKES)
    assert calls == [("app",), probe, *retakes, ("stop_load",), ("stop",)]


def test_failed_sessions_are_never_retaken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    failed = make_load_result(
        lag_s=STALLED.lag_s, session_errors=["session 3: the websocket closed"]
    )
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.latency",
        {"manager": "memory", "sessions": "10", "rate": "500"},
        {"closed": CLOSED, "open": failed},
    )
    assert entry["status"] == "failed"
    assert "1 of 10 sessions failed" in entry["error"]
    assert calls.count(("run", "open", 500.0, suite.LATENCY_WINDOW)) == 1


def test_a_failed_probe_stops_the_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    saturated = make_load_result(
        mode="closed",
        offered_rate=None,
        response_s=None,
        lag_s=None,
        generator_cpu_fraction=0.9,
    )
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.knee",
        {"manager": "memory", "sessions": "10"},
        {"closed": saturated},
    )
    assert entry["status"] == "failed"
    assert "generator saturated" in entry["error"]
    probe = ("run", "closed", None, suite.PROBE_WINDOW)
    # A saturated generator fails every attempt; cleanup stops the backend.
    assert calls == [("app",), *[probe] * (1 + suite.RETAKES), ("stop",)]


def test_capacity_reports_throughput_and_cpu_per_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    entry = run_capacity(tmp_path, monkeypatch, CLOSED)
    assert entry["status"] == "ok", entry["error"]
    metrics = entry["metrics"]
    assert metrics["throughput"]["samples"]["A"] == [1200.0]
    assert metrics["service_p50"]["samples"]["A"] == [0.003]
    assert metrics["cpu_us_per_event"]["samples"]["A"] == [pytest.approx(1e-4)]
    (extra,) = entry["sample_extra"]
    assert extra["answered"] == 12_000
    assert extra["cpu_method"] in {"cgroup", "psutil"}
    assert "pinning" in extra


def test_a_saturated_generator_fails_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    saturated = make_load_result(
        mode="closed",
        offered_rate=None,
        response_s=None,
        lag_s=None,
        generator_cpu_fraction=0.9,
    )
    entry = run_capacity(tmp_path, monkeypatch, saturated)
    assert entry["status"] == "failed"
    assert entry["error"].startswith("GeneratorSaturated: generator saturated: ")
    assert '"generator_cpu_fraction": 0.9' in entry["error"]


def test_failed_sessions_fail_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    failed = make_load_result(
        mode="closed",
        offered_rate=None,
        response_s=None,
        lag_s=None,
        session_errors=["session 3: the websocket closed"],
    )
    entry = run_capacity(tmp_path, monkeypatch, failed)
    assert entry["status"] == "failed"
    assert "1 of 10 sessions failed: session 3: the websocket closed" in entry["error"]
