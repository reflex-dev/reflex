"""Tests for reflex_bench.suites.events.

Nothing here starts a reflex app: the app and load hooks are replaced where a
test runs a benchmark through the scheduler. ``test_events_app.py`` runs them
for real.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from reflex_bench import registry
from reflex_bench.drivers.events import LoadResult
from reflex_bench.scheduler import Planned, Policy, Scheduler, plan
from reflex_bench.suites import events as suite

from tests.units.reflex_bench.factories import make_load_result, make_subject

SHAPES = ("background", "complex", "cross", "simple")


def names(suite_name: str | None, *filters: str) -> list[str]:
    selected = registry.select(registry.discover().values(), filters, suite_name)
    return [planned.name for planned in plan(selected, suite=suite_name)]


def test_instance_ids_and_params():
    everything = names(None, "events.*")
    assert suite.MANAGERS[:2] == ("memory", "disk")
    assert len(everything) == len(suite.MANAGERS) * (4 * (4 + 4 + 4) + 3)
    assert "events.simple.capacity[manager=memory,sessions=1]" in everything
    assert "events.simple.capacity[manager=disk,sessions=200]" in everything
    assert "events.cross.latency[manager=memory,sessions=10,rate=auto]" in everything
    assert "events.background.knee[manager=disk,sessions=50]" in everything
    assert "events.sessions.at_1hz[manager=memory,sessions=1000]" in everything


def test_smoke_runs_one_point_of_the_simple_shape():
    expected = [
        *(f"events.simple.capacity[manager={m},sessions=10]" for m in suite.MANAGERS),
        *(
            f"events.simple.latency[manager={m},sessions=10,rate=50]"
            for m in suite.MANAGERS
        ),
    ]
    assert names("smoke", "events.*") == expected


def test_suites():
    found = registry.discover()
    for shape in SHAPES:
        smoke = ("smoke",) if shape == "simple" else ()
        assert found[f"events.{shape}.capacity"].suites == (*smoke, "daily")
        assert found[f"events.{shape}.latency"].suites == (*smoke, "daily")
        # The knee only runs with --suite all or by name.
        assert found[f"events.{shape}.knee"].suites == ()
    assert found["events.sessions.at_1hz"].suites == ("daily",)
    assert found["selftest.events.calibrate"].suites == ("selftest",)
    assert "events.sessions.at_1hz[manager=memory,sessions=50]" in names("all")
    assert "events.simple.knee[manager=memory,sessions=10]" in names("all")


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


def run_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: LoadResult
) -> dict[str, Any]:
    """Run events.simple.capacity through the scheduler with a canned load result.

    Args:
        tmp_path: The bench home.
        monkeypatch: Replaces the app and the load.
        result: What the load returns.

    Returns:
        The result entry.
    """
    started: list[str] = []
    stopped: list[str] = []
    monkeypatch.setattr(suite, "prepare_app", lambda ctx: None)
    monkeypatch.setattr(suite._Sample, "start_app", lambda self: started.append("app"))
    monkeypatch.setattr(suite._Sample, "run", lambda self, *args: (result, 1.2))
    monkeypatch.setattr(suite._Sample, "stop", lambda self: stopped.append("stop"))
    bench = registry.discover()["events.simple.capacity"]
    (params,) = bench.expand({"manager": "memory", "sessions": "10"})
    runner = Scheduler(make_subject(), Policy(runs=1), home=tmp_path, seed=1)
    entry = runner.run_one(Planned(bench, params))
    # conclude stops what prepare started, also after a failed sample.
    assert started == ["app"]
    assert stopped == ["stop"]
    return dict(entry)


def test_capacity_reports_throughput_and_cpu_per_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    closed = make_load_result(
        mode="closed",
        offered_rate=None,
        response_s=None,
        lag_s=None,
        answered=12_000,
        answered_rate=1200.0,
    )
    entry = run_capacity(tmp_path, monkeypatch, closed)
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
