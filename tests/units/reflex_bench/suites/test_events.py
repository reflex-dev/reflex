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
from reflex_bench import cli, fixtures, registry
from reflex_bench.drivers.events import LoadResult, Mode
from reflex_bench.scheduler import Planned, Policy, Scheduler, plan
from reflex_bench.suites import events as suite

from tests.units.reflex_bench.factories import make_load_result, make_subject

SHAPES = ("background", "complex", "cross", "simple")
CHEAP = [
    "events.simple.capacity[manager=memory,sessions=10]",
    "events.simple.latency[manager=memory,sessions=10,rate=500]",
]
# The shared state points daily adds: contention at the cheap point, and the
# fan-out at two of its sizes.
DAILY_SHARED = [
    "events.shared_contention.capacity[manager=memory,sessions=10]",
    "events.shared_contention.latency[manager=memory,sessions=10,rate=auto]",
    "events.shared_fanout.broadcast[manager=memory,linked=5]",
    "events.shared_fanout.broadcast[manager=memory,linked=25]",
]


def selected(suite_name: str | None, *filters: str) -> list[Planned]:
    chosen = registry.select(registry.discover().values(), filters, suite_name)
    return plan(chosen, suite=suite_name)


def names(suite_name: str | None, *filters: str) -> list[str]:
    return [planned.name for planned in selected(suite_name, *filters)]


def test_instance_ids_and_params():
    everything = names(None, "events.*")
    assert suite.MANAGERS[:2] == ("memory", "disk")
    # Capacity and latency per shape (contention included), one knee (simple),
    # the 1 Hz sessions and the fan-out sizes.
    assert len(everything) == len(suite.MANAGERS) * (5 * (4 + 4) + 4 + 3 + 4)
    assert "events.simple.capacity[manager=memory,sessions=1]" in everything
    assert "events.simple.capacity[manager=disk,sessions=200]" in everything
    assert "events.cross.latency[manager=memory,sessions=10,rate=auto]" in everything
    assert "events.simple.knee[manager=disk,sessions=50]" in everything
    assert "events.sessions.at_1hz[manager=memory,sessions=1000]" in everything
    assert "events.shared_contention.capacity[manager=disk,sessions=200]" in everything
    assert (
        "events.shared_contention.latency[manager=memory,sessions=50,rate=auto]"
        in everything
    )
    for linked in (1, 5, 25, 100):
        assert f"events.shared_fanout.broadcast[manager=memory,linked={linked}]" in (
            everything
        )
    assert not [name for name in everything if name.startswith("events.cross.knee")]
    assert not [name for name in everything if "shared_fanout.capacity" in name]


def test_smoke_runs_two_cheap_points_and_daily_adds_the_shared_state():
    assert names("smoke", "events.*") == CHEAP
    assert sorted(names("daily", "events.*")) == sorted(CHEAP + DAILY_SHARED)


def test_daily_events_fit_the_ci_budget():
    # The estimate `list` shows with the default policy (10 runs at least).
    total = sum(
        cli._estimate(p.benchmark, Policy()) for p in selected("daily", "events.*")
    )
    assert total <= 6 * 60


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
    # The shared state shapes need the playground's board: daily and all, never pr.
    assert found["events.shared_contention.capacity"].suites == ("daily",)
    assert found["events.shared_contention.latency"].suites == ("daily",)
    assert found["events.shared_fanout.broadcast"].suites == ("daily",)
    assert not names("pr", "events.*")
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
    assert all(shape.client_var is None for shape in suite.SHAPES.values())


def test_the_shared_shapes_are_the_board_handler():
    board = "reflex___state____state.playground___state____board_state"
    fanout, contention = (
        suite.SHARED_SHAPES["shared_fanout"],
        suite.SHARED_SHAPES["shared_contention"],
    )
    for shape in (fanout, contention):
        assert shape.name == f"{board}.set_seq_shared"
        assert (shape.delta_key, shape.seq_var) == (board, "last_seq_rx_state_")
        assert shape.payload(7) == {"seq": 7}
        assert shape.ordered
    # Every linked session receives the fan-out; a contending session takes
    # only its own echo.
    assert fanout.client_var is None
    assert contention.client_var == "last_client_rx_state_"
    # The board's linked clients are wiped by a fresh token per load.
    link, again = suite.join_link(), suite.join_link()
    assert link.name == f"{board}.join"
    assert link.delta_key == board
    assert link.payload["token"] != again.payload["token"]
    assert "_" not in link.payload["token"]


class FakeRunner:
    """A load runner that records its plan and answers with a canned result."""

    plans: list[Any] = []

    def __init__(self, plan: Any) -> None:
        """Record the plan.

        Args:
            plan: The load plan.
        """
        self.plans.append(plan)

    def run(self, on_window: Any = None) -> LoadResult:
        """Answer with the canned result.

        Args:
            on_window: Ignored.

        Returns:
            The result.
        """
        return CLOSED


def test_a_linked_backend_joins_a_fresh_board_per_load(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(suite, "LoadRunner", FakeRunner)
    monkeypatch.setattr(FakeRunner, "plans", [])
    ctx = cast("Any", SimpleNamespace(params={"manager": "memory"}))
    shared = suite._Backend(
        ctx, suite.SHARED_SHAPES["shared_fanout"], sessions=25, linked=True
    )
    shared.url = "http://127.0.0.1:1"
    shared.run("fanout", None, suite.PROBE_WINDOW)
    shared.run("fanout", None, suite.FANOUT_WINDOW)
    private = suite._Backend(ctx, suite.SHAPES["simple"], sessions=50)
    private.url = shared.url
    private.run("closed", None, suite.PROBE_WINDOW)
    first, second, plain = FakeRunner.plans
    assert first.link is not None
    assert second.link is not None
    assert first.link.name == suite.join_link().name
    assert first.link.payload["token"] != second.link.payload["token"]
    assert (first.sessions, first.processes, first.mode) == (25, 1, "fanout")
    assert plain.link is None
    assert plain.sessions == 50


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
def test_split_cpus_without_topology(allowed, expected):
    assert suite.split_cpus(allowed, cores=None) == expected


def test_split_cpus_gives_whole_cores_to_each_side():
    # A Ryzen 5600: CPUs 6-11 are the SMT siblings of 0-5. Neither side gets a
    # sibling of the other side's core.
    cores = [[cpu, cpu + 6] for cpu in range(6)]
    assert suite.split_cpus(range(12), cores=cores) == {
        "server": [1, 2, 6, 7, 8],
        "generator": [3, 4, 5, 9, 10, 11],
    }
    # Two cores with SMT: one each.
    assert suite.split_cpus([0, 1, 2, 3], cores=[[0, 2], [1, 3]]) == {
        "server": [2],
        "generator": [1, 3],
    }


def test_split_cpus_is_none_when_cpu_0_is_the_server_side():
    # A cpuset of CPU 0 alone from its core plus three CPUs of later cores:
    # the lower half is CPU 0's core, which the server may not use.
    assert suite.split_cpus([0, 2, 3, 6], cores=[[0], [2, 3], [6]]) is None


def fake_sysfs(tmp_path: Path, siblings: dict[int, str]) -> Path:
    for cpu, listing in siblings.items():
        topology = tmp_path / f"cpu{cpu}" / "topology"
        topology.mkdir(parents=True)
        (topology / "thread_siblings_list").write_text(listing + "\n")
    return tmp_path


def test_cpu_cores_groups_smt_siblings_from_sysfs(tmp_path: Path):
    sysfs = fake_sysfs(
        tmp_path, {0: "0,4", 4: "0,4", 1: "1,5", 5: "1,5", 2: "2-3", 3: "2-3"}
    )
    assert suite.cpu_cores([0, 1, 2, 3, 4, 5], sysfs) == [[0, 4], [1, 5], [2, 3]]
    # A CPU outside the allowed set is left out of its core.
    assert suite.cpu_cores([0, 1, 2, 3, 5], sysfs) == [[0], [1, 5], [2, 3]]


def test_cpu_cores_is_none_without_a_readable_topology(tmp_path: Path):
    assert suite.cpu_cores([0, 1, 2, 3], tmp_path) is None
    assert suite.cpu_cores([0, 1, 2, 3], fake_sysfs(tmp_path, {0: "0"})) is None


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
    monkeypatch.setattr(
        suite._Backend, "start_echo", lambda self: calls.append(("echo",))
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
    assert entry["dims"] == {"fixture": "playground"}
    assert entry["fixture_hash"] == fixtures.fixture_hash("playground")
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


def test_a_load_the_self_check_rejects_fails_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # A stalled generator contaminates the tail; the sample fails at once and
    # is never taken again, which would drop the stall windows from the tails.
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.simple.latency",
        {"manager": "memory", "sessions": "10", "rate": "500"},
        {"closed": CLOSED, "open": [STALLED, make_load_result()]},
    )
    assert entry["status"] == "failed"
    assert entry["error"].startswith(
        "GeneratorSaturated: generator saturated: send lag"
    )
    probe = ("run", "closed", None, suite.PROBE_WINDOW)
    load = ("run", "open", 500.0, suite.LATENCY_WINDOW)
    assert calls == [("app",), probe, load, ("stop_load",), ("stop",)]


def test_failed_sessions_fail_the_latency_sample(
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
    assert calls == [("app",), probe, ("stop",)]


def test_calibration_offers_three_times_the_highest_suite_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # at_1hz with 1000 sessions offers 1000 ev/s, the highest fixed rate.
    assert pytest.approx(3000.0) == suite.CALIBRATION_RATE
    step = make_load_result(offered_rate=3000.0, achieved_send_rate=2999.0)
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "selftest.events.calibrate",
        {},
        {"closed": CLOSED, "open": step},
    )
    assert entry["status"] == "ok", entry["error"]
    closed = ("run", "closed", None, suite.CALIBRATION_CLOSED_WINDOW)
    opened = ("run", "open", 3000.0, suite.CALIBRATION_STEP_WINDOW)
    assert calls == [("echo",), closed, opened, ("stop_load",), ("stop",)]
    metrics = entry["metrics"]
    assert metrics["closed_ceiling"]["samples"]["A"] == [1200.0]
    assert metrics["open_lag_p99"]["samples"]["A"] == [0.00021]
    (extra,) = entry["sample_extra"]
    assert extra["open"]["offered_rate"] == pytest.approx(3000.0)
    assert "steps" not in extra


def test_calibration_fails_when_the_generator_cannot_offer_the_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "selftest.events.calibrate",
        {},
        {"closed": CLOSED, "open": STALLED},
    )
    assert entry["status"] == "failed"
    assert entry["error"].startswith("GeneratorSaturated: generator saturated")
    assert calls[-1] == ("stop",)


def test_capacity_reports_throughput_and_cpu_per_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    entry = run_capacity(tmp_path, monkeypatch, CLOSED)
    assert entry["status"] == "ok", entry["error"]
    metrics = entry["metrics"]
    assert metrics["throughput"]["samples"]["A"] == [1200.0]
    assert metrics["service_p50"]["samples"]["A"] == [0.003]
    assert metrics["cpu_per_event"]["samples"]["A"] == [pytest.approx(1e-4)]
    (extra,) = entry["sample_extra"]
    assert extra["answered"] == 12_000
    assert extra["cpu_method"] in {"cgroup", "psutil"}
    assert "pinning" in extra
    # The histogram pools over runs; the per-second counts are a run's own.
    assert "histogram" in extra
    assert "answered_per_second" not in extra


FANOUT = make_load_result(
    mode="fanout",
    sessions=25,
    offered_rate=None,
    response_s=None,
    lag_s=None,
    answered=600,
    answered_rate=200.0,
    service_s={"p50": 0.004, "p99": 0.011, "max": 0.02},
    spread_s={"p50": 0.0015, "p99": 0.004, "max": 0.006},
)


def test_fanout_reports_the_broadcast_time_and_spread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    entry, calls = run_instance(
        tmp_path,
        monkeypatch,
        "events.shared_fanout.broadcast",
        {"manager": "memory", "linked": "25"},
        {"fanout": FANOUT},
    )
    assert entry["status"] == "ok", entry["error"]
    # The warm-up probe is a fan-out too, and the sample counts one sender.
    assert calls[:2] == [("app",), ("run", "fanout", None, suite.PROBE_WINDOW)]
    assert calls[2] == ("run", "fanout", None, suite.FANOUT_WINDOW)
    assert calls[-1] == ("stop",)
    metrics = entry["metrics"]
    assert metrics["throughput"]["samples"]["A"] == [200.0]
    assert metrics["broadcast_p50"]["samples"]["A"] == [0.004]
    assert metrics["broadcast_p99"]["samples"]["A"] == [0.011]
    assert metrics["fanout_spread_p50"]["samples"]["A"] == [0.0015]
    assert metrics["cpu_per_event"]["samples"]["A"] == [pytest.approx(1.2 / 600)]
    (extra,) = entry["sample_extra"]
    assert extra["spread_s"] == FANOUT.spread_s
    assert extra["p99_underpowered"] is True


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
