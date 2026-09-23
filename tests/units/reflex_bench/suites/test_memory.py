"""Tests for reflex_bench.suites.memory.

Nothing here starts reflex, a generator or a cgroup scope: the suite's drivers
and collectors are replaced with fakes that log what happens, in order.
``test_memory_app.py`` runs the benchmarks for real.
"""

from __future__ import annotations

import dataclasses
import functools
import math
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from reflex_bench import registry
from reflex_bench.collectors import pss
from reflex_bench.collectors.cgroup import CgroupReading
from reflex_bench.collectors.pss import PssReading, PssResult
from reflex_bench.context import Context
from reflex_bench.drivers.app_process import AppStartError, CliResult
from reflex_bench.drivers.events import LoadPlan, LoadResult
from reflex_bench.scheduler import Planned, Policy, Scheduler, plan
from reflex_bench.suites import events as events_suite
from reflex_bench.suites import memory

from tests.units.reflex_bench.collectors.test_pss import (  # noqa: F401 - tree is a fixture
    _fake,
    _rollup,
    tree,
)
from tests.units.reflex_bench.factories import (
    make_context,
    make_load_result,
    make_subject,
)

MIB = 1024**2
APP_PID = 1001
ECHO_PID = 2002
# The fake server grows by this much per held session, the echo server by less.
PER_SESSION = 40_000
ECHO_PER_SESSION = 9_000


def names(suite: str | None, *filters: str) -> list[str]:
    selected = registry.select(registry.discover().values(), filters, suite)
    return [planned.name for planned in plan(selected, suite=suite)]


def test_instance_ids_per_suite():
    managers = memory.MANAGERS
    assert managers[:2] == ("memory", "disk")
    assert names("smoke", "memory.*") == ["memory.idle[manager=memory]"]
    assert names("pr", "memory.*") == []
    assert names("daily", "memory.*") == [
        "memory.boot_512mb[manager=memory]",
        "memory.compile.peak[command=compile]",
        "memory.compile.peak[command=export]",
        *(f"memory.idle[manager={m}]" for m in managers),
        *(f"memory.leak[manager={m},events=50000]" for m in managers),
        *(f"memory.per_session[manager={m},max_sessions=500]" for m in managers),
    ]
    assert names("all", "memory.*") == [
        "memory.boot.min_limit[manager=memory]",
        *(f"memory.boot_512mb[manager={m}]" for m in managers),
        "memory.compile.peak[command=compile]",
        "memory.compile.peak[command=export]",
        *(f"memory.idle[manager={m}]" for m in managers),
        "memory.idle.allocator[allocator=mimalloc]",
        "memory.idle.allocator[allocator=arena2]",
        *(f"memory.leak[manager={m},events=100000]" for m in managers),
        *(f"memory.per_session[manager={m},max_sessions=1000]" for m in managers),
    ]
    assert "memory.per_session[manager=disk,max_sessions=1000]" in names(None)


def test_the_managers_are_the_event_suites():
    # redis joins when REFLEX_REDIS_URL is set as the suites are imported.
    assert events_suite.managers(os.environ) == memory.MANAGERS
    found = registry.discover()
    for bench_id in ("memory.idle", "memory.per_session", "memory.leak"):
        assert found[bench_id].params["manager"] == memory.MANAGERS


def test_declarations():
    found = registry.discover()
    assert {bench_id: bench.warmup for bench_id, bench in found.items() if bench_id.startswith("memory.")} == {
        "memory.boot.min_limit": 0,
        "memory.boot_512mb": 0,
        "memory.compile.peak": 1,
        "memory.idle": 0,
        "memory.idle.allocator": 0,
        "memory.leak": 0,
        "memory.per_session": 0,
    }  # fmt: skip
    assert found["memory.leak"].timeout == 900
    assert found["memory.per_session"].timeout == 600
    assert found["memory.boot.min_limit"].timeout == 600
    assert found["memory.compile.peak"].timeout > memory.COMPILE_TIMEOUT_S
    for bench_id, bench in found.items():
        if not bench_id.startswith("memory."):
            continue
        assert bench.setup_timeout == 900
        # Memory only: no timing metric, and every byte count is lower-is-better.
        assert "wall" not in bench.metrics
        assert bench.kind in {"peakmem", "track"}
        for metric in bench.metrics.values():
            assert (metric.unit, metric.direction) in {("B", "lower"), ("1", "higher")}
    passed = found["memory.boot_512mb"].metrics["passed"]
    assert (passed.assume, passed.direction) == ("exact", "higher")
    # The allocator variants reuse the idle benchmark.
    assert found["memory.idle.allocator"].cls is found["memory.idle"].cls


@pytest.mark.parametrize(
    ("largest", "counts"),
    [
        (1000, (0, 100, 500, 1000)),
        (500, (0, 100, 500)),
        (200, (0, 100, 200)),
        # Three counts at least, so the fit has an interval.
        (50, (0, 25, 50)),
        (2, (0, 1, 2)),
    ],
)
def test_sessions_sweep(largest: int, counts: tuple[int, ...]):
    assert memory.sessions_sweep(largest) == counts


def test_a_sweep_needs_two_sessions():
    with pytest.raises(ValueError, match="at least 2 sessions"):
        memory.sessions_sweep(1)


def context(tmp_path: Path, **params: Any) -> Context:
    ctx = make_context(tmp_path, {"manager": "memory", **params})
    ctx.env = {
        "PATH": "/venv/bin",
        "PYTHONMALLOC": "debug",
        "REFLEX_REDIS_URL": "redis://localhost:6379",
    }
    return ctx


def test_server_env(tmp_path: Path):
    env = memory.server_env(context(tmp_path))
    assert env["REFLEX_STATE_MANAGER_MODE"] == "memory"
    assert env["GRANIAN_WORKERS"] == "1"
    assert env["REFLEX_STATES_WORKDIR"] == str(tmp_path / "states")
    assert env["REFLEX_WEB_WORKDIR"] == str(tmp_path / "web")
    assert env["PATH"] == "/venv/bin"
    # The default allocator is the interpreter's, whatever the shell sets.
    assert "PYTHONMALLOC" not in env
    assert "MALLOC_ARENA_MAX" not in env
    assert "REFLEX_REDIS_URL" not in env
    assert "REFLEX_REDIS_TOKEN_EXPIRATION" not in env
    redis = memory.server_env(context(tmp_path, manager="redis"))
    assert redis["REFLEX_REDIS_URL"] == "redis://localhost:6379"
    assert redis["GRANIAN_WORKERS"] == "1"
    arena = memory.server_env(context(tmp_path, allocator="arena2"))
    assert arena["MALLOC_ARENA_MAX"] == "2"
    expiring = memory.server_env(context(tmp_path), REFLEX_REDIS_TOKEN_EXPIRATION="120")
    assert expiring["REFLEX_REDIS_TOKEN_EXPIRATION"] == "120"


def test_mimalloc_needs_python_3_13(tmp_path: Path):
    ctx = context(tmp_path, allocator="mimalloc")
    # The factory's subject runs Python 3.12.8.
    with pytest.raises(ValueError, match=r"needs Python 3\.13 or later.*3\.12\.8"):
        memory.server_env(ctx)
    ctx.subject = dataclasses.replace(ctx.subject, python_version="3.13.1")
    assert memory.server_env(ctx)["PYTHONMALLOC"] == "mimalloc"
    with pytest.raises(ValueError, match="unknown allocator 'jemalloc'"):
        memory.allocator_env("jemalloc", "3.14.0")


def reading(**changes: Any) -> CgroupReading:
    values: dict[str, Any] = {
        "memory_peak_bytes": 300 * MIB,
        "memory_current_bytes": 200 * MIB,
        "anon_bytes": 150 * MIB,
        "file_bytes": 40 * MIB,
        "oom": 0,
        "oom_kill": 0,
        "cpu_usage_usec": 1_000_000,
        "cpu_user_usec": 900_000,
        "cpu_system_usec": 100_000,
        "peak_reset": False,
    }
    return CgroupReading(**{**values, **changes})


def pss_reading(total: int, anon: int | None = None) -> PssReading:
    anon = int(total * 0.85) if anon is None else anon
    return PssReading(
        pss_bytes=total,
        pss_anon_bytes=anon,
        pss_file_bytes=total - anon,
        uss_bytes={"python": total - 10 * MIB},
        processes=4,
    )


def closed_result(plan: LoadPlan) -> LoadResult:
    """Answer a closed-loop load plan healthily.

    Args:
        plan: The plan.

    Returns:
        The result.
    """
    return make_load_result(
        mode="closed", offered_rate=None, response_s=None, lag_s=None
    )


@dataclasses.dataclass
class Fakes:
    """The fake drivers and collectors, and what they saw.

    Attributes:
        log: What happened, in order.
        scope_reason: What ``CgroupScope.available()`` says; ``None`` means
            scopes work.
        oom_kill_at: The limited phase (compile, boot, serve) whose reading
            counts an OOM kill.
        fail_start: Makes the server's start fail as an OOM-killed root would.
        held: Sessions the fake holds keep on each server, by pid.
        envs: The environment of every started server.
        scopes: Every scope created: limit and swap.
        plans: Every load plan run.
        load: Builds the result of a load plan.
        answer_load: Makes loads call ``on_window`` and take the window's time.
        grow: The server's anonymous memory growth per second of load.
        loading_since: When the last load with a window started.
        app_pid: The pid the fake server reports.
    """

    log: list[str] = dataclasses.field(default_factory=list)
    scope_reason: str | None = "no cgroup v2 here"
    oom_kill_at: str | None = None
    fail_start: bool = False
    held: dict[int, int] = dataclasses.field(default_factory=dict)
    envs: list[dict[str, str]] = dataclasses.field(default_factory=list)
    scopes: list[tuple[int | None, int | None]] = dataclasses.field(
        default_factory=list
    )
    plans: list[LoadPlan] = dataclasses.field(default_factory=list)
    load: Callable[[LoadPlan], LoadResult] = closed_result
    answer_load: bool = False
    grow: float = 0.0
    loading_since: float | None = None
    app_pid: int = APP_PID

    def tree_pss(self, pid: int) -> PssReading:
        """Read a fake server tree: its sessions and its load show.

        Args:
            pid: The server (the app or the echo server).

        Returns:
            The reading.
        """
        per_session = ECHO_PER_SESSION if pid == ECHO_PID else PER_SESSION
        base = 20 * MIB if pid == ECHO_PID else 150 * MIB
        total = base + per_session * self.held.get(pid, 0)
        grown = 0
        if self.loading_since is not None:
            grown = int(self.grow * (time.perf_counter() - self.loading_since))
        return pss_reading(total + grown, int(total * 0.85) + grown)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    """Replace every driver and collector the suite uses.

    Returns:
        The fakes.
    """
    state = Fakes()
    phases = iter(("compile", "boot", "serve"))
    log = state.log

    class FakeScope:
        def __init__(self, *, limit_bytes: int | None = None, swap_max: int | None = 0):
            if state.scope_reason is not None:
                msg = f"cgroup scopes are unavailable: {state.scope_reason}"
                raise RuntimeError(msg)
            self.limit_bytes = limit_bytes
            state.scopes.append((limit_bytes, swap_max))

        @staticmethod
        def available() -> str | None:
            return state.scope_reason

        def read(self) -> CgroupReading:
            phase = next(phases) if self.limit_bytes is not None else "unlimited"
            log.append(f"read {phase}")
            return reading(oom_kill=int(phase == state.oom_kill_at))

    def run_cli(python, args, *, cwd, env, timeout, scope=None, phases=False, sample_memory=False):  # fmt: skip
        log.append(f"run_cli {args[0]}")
        if scope is not None:
            cgroup = scope.read()
            return CliResult(
                args=list(args), returncode=137 if cgroup.oom_kill else 0,
                wall_s=1.0, lines=["Compiling"], timeout_s=timeout,
                peak_mem_bytes=cgroup.memory_peak_bytes, memory_method="cgroup",
                cgroup=cgroup,
            )  # fmt: skip
        sampled = None
        if sample_memory:
            peak = pss_reading(400 * MIB)
            peak = dataclasses.replace(
                peak, uss_bytes={"python": 90 * MIB, "bun": 200 * MIB}
            )
            sampled = PssResult(
                peak_bytes=400 * MIB,
                peak=peak,
                timeline=[],
                samples=31,
                interval_s=0.05,
            )
        return CliResult(
            args=list(args), returncode=0, wall_s=1.0, lines=[], timeout_s=timeout,
            peak_mem_bytes=sampled.peak_bytes if sampled else None,
            memory_method=sampled.method if sampled else None, pss=sampled,
        )  # fmt: skip

    class FakeApp:
        def __init__(self, python, app_dir, *, mode, reflex_version, env, backend_only, scope, start_timeout):  # fmt: skip
            assert (mode, backend_only) == ("prod", True)
            state.envs.append(env)
            self.pid = state.app_pid
            self.backend_url = "http://localhost:8000"
            self.running = False

        def start(self) -> None:
            log.append("app start")
            if state.fail_start:
                msg = "reflex run exited with code -9 before it was ready\nKilled"
                raise AppStartError(msg, ["Starting", "Killed"])
            self.running = True

        def wait_http_ready(self, timeout: float) -> float:
            return 1.0

        def is_running(self) -> bool:
            return self.running

        def logs(self) -> list[str]:
            return ["App running at: http://0.0.0.0:8000"]

        def stop(self) -> None:
            log.append("app stop")
            self.running = False

    class FakeRunner:
        def __init__(self, plan: LoadPlan):
            self.plan = plan

        def run(self, on_window=None) -> LoadResult:
            state.plans.append(self.plan)
            log.append(f"load {self.plan.sessions}x{self.plan.duration_s:g}s")
            if state.answer_load and on_window is not None:
                state.loading_since = time.perf_counter()
                time.sleep(self.plan.warmup_s)
                on_window("start")
                time.sleep(self.plan.duration_s)
                on_window("end")
            return state.load(self.plan)

        def stop(self) -> None:
            log.append("load stop")

    class FakeHold:
        def __init__(self, url: str, count: int):
            self.pid = ECHO_PID if url == "http://echo" else APP_PID
            self.count = count
            self.open = False

        def ready(self) -> None:
            log.append(f"hold {self.count}")
            state.held[self.pid] = state.held.get(self.pid, 0) + self.count
            self.open = True

        def close(self) -> list[str]:
            log.append(f"close {self.count}")
            self.open = False
            return []

        def kill(self) -> None:
            log.append(f"kill hold {self.count}")

    class FakeEcho:
        def __init__(self, *, delta_key: str, seq_var: str):
            self.pid = ECHO_PID

        def start(self) -> str:
            log.append("echo start")
            return "http://echo"

        def stop(self) -> None:
            log.append("echo stop")

    monkeypatch.setattr(memory, "CgroupScope", FakeScope)
    monkeypatch.setattr(memory, "run_cli", run_cli)
    monkeypatch.setattr(memory, "AppProcess", FakeApp)
    monkeypatch.setattr(memory, "LoadRunner", FakeRunner)
    monkeypatch.setattr(
        memory,
        "hold_sessions",
        lambda url, count, *, reflex_version: FakeHold(url, count),
    )
    monkeypatch.setattr(memory, "EchoProcess", FakeEcho)
    monkeypatch.setattr(memory, "tree_pss", state.tree_pss)
    monkeypatch.setattr(memory, "largest_uss", lambda pid: 60 * MIB)
    monkeypatch.setattr(memory, "copy_app", lambda target: None)
    monkeypatch.setattr(memory, "SETTLE_S", 0.0)
    monkeypatch.setattr(memory, "READ_INTERVAL_S", 0.0)
    monkeypatch.setattr(memory, "EXPIRY_MARGIN_S", 0.0)
    return state


def run(tmp_path: Path, bench_id: str, **params: Any) -> dict[str, Any]:
    """Run one instance through the scheduler, one timed sample, no warmup.

    Args:
        tmp_path: The bench home.
        bench_id: The benchmark id.
        **params: Parameter overrides.

    Returns:
        The result entry.
    """
    bench = registry.discover()[bench_id]
    overrides = {"manager": "memory", **params}
    (params_set,) = bench.expand({key: str(value) for key, value in overrides.items()})
    policy = Policy(runs=1, warmup=0)
    runner = Scheduler(make_subject(), policy, home=tmp_path, seed=1)
    return dict(runner.run_one(Planned(bench, params_set)))


def test_compile_peak_with_a_scope_reads_the_cgroup(tmp_path: Path, fakes: Fakes):
    fakes.scope_reason = None
    entry = run(tmp_path, "memory.compile.peak", command="export")
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"memory_method": "cgroup"}
    assert entry["metrics"]["peak_mem"]["samples"]["A"] == [300 * MIB]
    (extra,) = entry["sample_extra"]
    assert extra == {
        "memory_method": "cgroup",
        "returncode": 0,
        "memory_current_bytes": 200 * MIB,
        "anon_bytes": 150 * MIB,
        "file_bytes": 40 * MIB,
        "memory_peak_bytes": 300 * MIB,
        "peak_reset": False,
    }
    # setup_cache compiled once, then the sample exported with no limit.
    assert fakes.log == ["run_cli compile", "run_cli export", "read unlimited"]
    assert fakes.scopes == [(None, 0)]


def test_compile_peak_without_a_scope_samples_pss(tmp_path: Path, fakes: Fakes):
    entry = run(tmp_path, "memory.compile.peak", command="compile")
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"memory_method": "pss_sampling"}
    assert entry["metrics"]["peak_mem"]["samples"]["A"] == [400 * MIB]
    (extra,) = entry["sample_extra"]
    assert extra["memory_method"] == "pss_sampling"
    assert extra["uss_bytes"] == {"python": 90 * MIB, "bun": 200 * MIB}
    assert extra["pss_samples"] == 31


@pytest.mark.parametrize("scope_reason", [None, "no cgroup v2 here"])
def test_idle_reads_the_settled_tree(
    tmp_path: Path, fakes: Fakes, scope_reason: str | None
):
    fakes.scope_reason = scope_reason
    entry = run(tmp_path, "memory.idle", manager="disk", idle_s=0)
    assert entry["status"] == "ok", entry["error"]
    # The values are the tree's PSS with or without a scope.
    assert entry["dims"] == {"memory_method": "pss_sampling"}
    metrics = entry["metrics"]
    assert metrics["pss"]["samples"]["A"] == [150 * MIB]
    assert metrics["pss_anon"]["samples"]["A"] == [int(150 * MIB * 0.85)]
    assert metrics["pss_file"]["samples"]["A"] == [150 * MIB - int(150 * MIB * 0.85)]
    (extra,) = entry["sample_extra"]
    assert extra["memory_method"] == "pss_sampling"
    assert extra["uss_bytes"] == {"python": 140 * MIB}
    assert extra["processes"] == 4
    assert extra["worker_uss_bytes"] == 60 * MIB
    assert ("memory_current_bytes" in extra) is (scope_reason is None)
    (env,) = fakes.envs
    assert env["REFLEX_STATE_MANAGER_MODE"] == "disk"
    assert env["GRANIAN_WORKERS"] == "1"
    assert "REFLEX_REDIS_TOKEN_EXPIRATION" not in env
    # The scope, when there is one, is read before the server stops.
    assert fakes.log[-2:] == (
        ["read unlimited", "app stop"]
        if scope_reason is None
        else ["app start", "app stop"]
    )


def test_an_allocator_variant_is_a_separate_series(tmp_path: Path, fakes: Fakes):
    entry = run(tmp_path, "memory.idle", idle_s=0, allocator="arena2")
    assert entry["status"] == "ok", entry["error"]
    assert entry["params"] == {"manager": "memory"}
    assert entry["dims"] == {"memory_method": "pss_sampling", "allocator": "arena2"}
    assert fakes.envs[0]["MALLOC_ARENA_MAX"] == "2"


def test_mimalloc_on_python_3_12_fails_the_sample(tmp_path: Path, fakes: Fakes):
    entry = run(tmp_path, "memory.idle.allocator", allocator="mimalloc", idle_s=0)
    assert entry["status"] == "failed"
    assert "PYTHONMALLOC=mimalloc needs Python 3.13 or later" in entry["error"]
    assert fakes.envs == []


def test_settled_pss_takes_the_median_of_three_reads(monkeypatch: pytest.MonkeyPatch):
    reads = iter([
        pss_reading(100, 80),
        pss_reading(300, 90),
        pss_reading(200, 150),
    ])
    monkeypatch.setattr(memory, "tree_pss", lambda pid: next(reads))
    monkeypatch.setattr(memory, "READ_INTERVAL_S", 0.0)
    settled = memory.settled_pss(APP_PID)
    assert (settled.pss_bytes, settled.pss_anon_bytes, settled.pss_file_bytes) == (
        200,
        90,
        # 20, 210 and 50: the file part's own median.
        50,
    )


def test_settled_pss_refuses_a_gone_tree(monkeypatch: pytest.MonkeyPatch):
    empty = PssReading(0, 0, 0, {}, 0)
    monkeypatch.setattr(memory, "tree_pss", lambda pid: empty)
    with pytest.raises(RuntimeError, match="is gone"):
        memory.settled_pss(APP_PID)


def test_idle_reads_a_real_tree_from_proc(
    tmp_path: Path,
    fakes: Fakes,
    tree: tuple[int, int],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
):
    parent, child = tree
    proc = tmp_path / "proc"
    _fake(proc, parent, "python", _rollup(50_000, 45_000, 5_000, 200, 44_800))
    _fake(proc, child, "python", _rollup(90_000, 75_000, 15_000, 8_000, 73_000))
    monkeypatch.setattr(
        memory, "tree_pss", functools.partial(pss.tree_pss, proc_root=proc)
    )
    fakes.app_pid = parent
    entry = run(tmp_path / "home", "memory.idle", idle_s=0)
    assert entry["status"] == "ok", entry["error"]
    metrics = entry["metrics"]
    assert metrics["pss"]["samples"]["A"] == [140_000 * 1024]
    assert metrics["pss_anon"]["samples"]["A"] == [120_000 * 1024]
    assert metrics["pss_file"]["samples"]["A"] == [20_000 * 1024]
    (extra,) = entry["sample_extra"]
    # USS per command name: the supervisor and the worker are both python.
    assert extra["uss_bytes"] == {"python": 126_000 * 1024}
    assert extra["processes"] == 2


def test_per_session_fits_the_sweep(tmp_path: Path, fakes: Fakes):
    entry = run(tmp_path, "memory.per_session", max_sessions=500, expiry_s=1)
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"memory_method": "pss_sampling"}
    metrics = entry["metrics"]
    assert metrics["bytes_per_session"]["samples"]["A"] == [pytest.approx(PER_SESSION)]
    assert metrics["bytes_per_session_ci_hi"]["samples"]["A"] == [
        pytest.approx(PER_SESSION)
    ]
    # The fake server never frees a session.
    assert metrics["residual_after_disconnect"]["samples"]["A"] == [500 * PER_SESSION]
    assert metrics["residual_after_expiry"]["samples"]["A"] == [500 * PER_SESSION]
    (extra,) = entry["sample_extra"]
    assert [level["sessions"] for level in extra["levels"]] == [0, 100, 500]
    assert extra["r2"] == pytest.approx(1.0)
    assert extra["baseline_bytes_per_session"] == pytest.approx(ECHO_PER_SESSION)
    assert [level["sessions"] for level in extra["baseline_levels"]] == [0, 100, 500]
    assert extra["session_errors"] == []
    assert extra["expiry_s"] == 1
    (env,) = fakes.envs
    assert env["REFLEX_REDIS_TOKEN_EXPIRATION"] == "1"
    # Monotone holds, closed before the residual; the echo floor meanwhile.
    assert fakes.log == [
        "run_cli compile",
        "app start",
        "hold 100",
        "hold 400",
        "close 100",
        "close 400",
        "echo start",
        "hold 100",
        "hold 400",
        "close 100",
        "close 400",
        "echo stop",
        # conclude: everything, newest first.
        "kill hold 400",
        "kill hold 100",
        "echo stop",
        "kill hold 400",
        "kill hold 100",
        "app stop",
    ]


def test_per_session_fails_when_the_sweep_outlasts_the_expiration(
    tmp_path: Path, fakes: Fakes, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(memory, "SETTLE_S", 0.4)
    entry = run(tmp_path, "memory.per_session", max_sessions=500, expiry_s=1)
    assert entry["status"] == "failed"
    assert "not less than the token expiration of 1 s" in entry["error"]
    assert fakes.log[-1] == "app stop"


def test_conclude_stops_the_holds_and_the_server_after_a_failure(
    tmp_path: Path, fakes: Fakes, monkeypatch: pytest.MonkeyPatch
):
    reads = 0

    def failing(pid: int) -> PssReading:
        nonlocal reads
        reads += 1
        # Three reads per level: the fifth level read is the 500 sessions'.
        if reads > 7:
            msg = "the process tree of pid 1001 is gone"
            raise RuntimeError(msg)
        return fakes.tree_pss(pid)

    monkeypatch.setattr(memory, "tree_pss", failing)
    entry = run(tmp_path, "memory.per_session", max_sessions=500)
    assert entry["status"] == "failed"
    assert "is gone" in entry["error"]
    assert fakes.log[-3:] == ["kill hold 400", "kill hold 100", "app stop"]


def leak_result(rate: float) -> Callable[[LoadPlan], LoadResult]:
    """Answer every planned second of a closed loop at a fixed rate.

    Args:
        rate: Events per second.

    Returns:
        The fake load's result builder.
    """

    def build(plan: LoadPlan) -> LoadResult:
        seconds = math.ceil(plan.warmup_s + plan.duration_s)
        answered = round(rate * plan.duration_s)
        return make_load_result(
            mode="closed", offered_rate=None, response_s=None, lag_s=None,
            sessions=plan.sessions, sent=answered, answered=answered,
            answered_rate=rate, warmup_s=plan.warmup_s, duration_s=plan.duration_s,
            answered_per_second=[round(rate)] * seconds,
        )  # fmt: skip

    return build


def test_a_leaking_server_fails_the_leak_gate(tmp_path: Path, fakes: Fakes):
    fakes.load = leak_result(1000.0)
    fakes.answer_load = True
    # 2 MB per second at 1000 events per second: 2 kB per event.
    fakes.grow = 2_000_000.0
    entry = run(tmp_path, "memory.leak", events=1000, warmup_events=0)
    assert entry["status"] == "failed"
    error = entry["error"]
    assert error.startswith("LeakDetected: memory grows by 2")
    assert "in the second half after" in error
    probe, measured = fakes.plans
    assert (probe.mode, probe.duration_s, probe.sessions) == ("closed", 5.0, 10)
    # 1000 events at the probe's 1000 ev/s, with 10 % of room: 2 s.
    assert (measured.warmup_s, measured.duration_s) == (0, 2)
    assert fakes.log[-2:] == ["load stop", "app stop"]


def test_a_flat_server_passes_the_leak_gate(tmp_path: Path, fakes: Fakes):
    fakes.load = leak_result(1000.0)
    fakes.answer_load = True
    entry = run(tmp_path, "memory.leak", events=1000, warmup_events=0)
    assert entry["status"] == "ok", entry["error"]
    assert entry["metrics"]["bytes_per_event"]["samples"]["A"] == [0.0]
    assert entry["metrics"]["growth"]["samples"]["A"] == [0.0]
    (extra,) = entry["sample_extra"]
    assert extra["memory_method"] == "pss_sampling"
    assert extra["samples"] >= 10
    assert extra["unanswered"] == 0
    assert extra["events_measured"] == 2000
    assert extra["warmup_events"] == 0
    assert "histogram" not in extra["generator"]
    assert "answered_per_second" not in extra["generator"]
    # [events, anonymous PSS, worker USS], events increasing over the window.
    timeline = extra["timeline"]
    assert timeline[0][1:] == [int(150 * MIB * 0.85), 60 * MIB]
    assert [point[0] for point in timeline] == sorted(point[0] for point in timeline)
    assert 0 <= timeline[0][0] < timeline[-1][0] <= 2000


def test_unanswered_events_fail_the_leak_sample(tmp_path: Path, fakes: Fakes):
    counted = leak_result(1000.0)
    fakes.load = lambda plan: dataclasses.replace(counted(plan), unanswered=3)
    entry = run(tmp_path, "memory.leak", events=1000, warmup_events=0)
    assert entry["status"] == "failed"
    assert "3 of 5000 events were not answered" in entry["error"]


def timeline(
    anon: Callable[[float], float], events: int = 50_000, samples: int = 100
) -> tuple[list[float], list[float]]:
    """Build a timeline of anonymous memory against events, with a little noise.

    Args:
        anon: Bytes at a given event count.
        events: The events of the window.
        samples: The number of samples.

    Returns:
        The events and the bytes of each sample.
    """
    xs = [events * index / (samples - 1) for index in range(samples)]
    # Deterministic noise of +-8 kB, well below one arena.
    ys = [
        60 * MIB + anon(x) + 8192 * math.sin(3.1 * index) for index, x in enumerate(xs)
    ]
    return xs, ys


def test_a_heap_that_warms_up_and_flattens_is_no_leak():
    # 12 MiB in the first 20 % of the window, then flat.
    leak = memory.fit_leak(*timeline(lambda x: 12 * MIB * min(x / 10_000, 1.0)))
    assert leak.fit.ci_hi > 100
    assert leak.second.slope < memory.SECOND_HALF_SHARE * leak.first.slope
    assert leak.verdict(100) is None


def test_a_steady_ramp_is_a_leak():
    leak = memory.fit_leak(*timeline(lambda x: 2048 * x))
    verdict = leak.verdict(100)
    assert verdict is not None
    assert "memory grows by 2048.0 B per event" in verdict
    assert "2048.0 B per event in the second half after 2048.0 in the first" in verdict


def test_one_arena_step_in_a_long_window_is_no_leak():
    # A 1 MiB step in the middle of 50 000 events is about 30 B per event.
    leak = memory.fit_leak(*timeline(lambda x: MIB * (x > 25_000)))
    assert 20 < leak.fit.slope < 40
    assert leak.fit.ci_hi < 100
    assert leak.verdict(100) is None


def test_a_leak_fit_needs_six_samples():
    with pytest.raises(ValueError, match="at least 6 samples"):
        memory.fit_leak([1.0, 2.0, 3.0, 4.0, 5.0], [1.0] * 5)


def test_events_at_interpolates_within_a_second():
    per_second = [100, 200, 50]
    assert memory.events_at(per_second, [-1.0, 0.0, 0.5, 1.0, 1.25, 2.5, 3.0, 9.0]) == [
        0.0,
        0.0,
        50.0,
        100.0,
        150.0,
        325.0,
        350.0,
        350.0,
    ]


def test_thin_keeps_the_ends():
    assert memory.thin(list(range(10)), 20) == list(range(10))
    assert memory.thin(list(range(1000)), 5) == [0, 250, 500, 749, 999]


def test_the_512mb_gate_needs_a_scope(tmp_path: Path, fakes: Fakes):
    entry = run(tmp_path, "memory.boot_512mb")
    assert entry["status"] == "failed"
    assert (
        entry["error"]
        == "RuntimeError: cgroup scopes are unavailable: no cgroup v2 here"
    )
    assert entry["dims"] == {"memory_method": "cgroup"}


def test_the_512mb_gate_passes_with_three_peaks(tmp_path: Path, fakes: Fakes):
    fakes.scope_reason = None
    entry = run(tmp_path, "memory.boot_512mb")
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"memory_method": "cgroup"}
    values = {name: metric["samples"]["A"] for name, metric in entry["metrics"].items()}
    assert values == {
        "passed": [1.0],
        "peak_compile": [300 * MIB],
        "peak_boot": [300 * MIB],
        "peak_serve": [300 * MIB],
    }
    (extra,) = entry["sample_extra"]
    assert extra["limit_mb"] == 512
    assert set(extra["phases"]) == {"compile", "boot", "serve"}
    assert all(phase["oom_kill"] == 0 for phase in extra["phases"].values())
    # Every limited scope is 512 MiB with swap off.
    assert fakes.scopes == [(512 * MIB, 0), (512 * MIB, 0)]
    # Each scope is read before its tree stops.
    assert fakes.log == [
        "run_cli compile",
        "run_cli compile",
        "read compile",
        "app start",
        "read boot",
        "load 5x5s",
        "read serve",
        "app stop",
        "load stop",
        "app stop",
    ]
    (serve,) = fakes.plans
    assert (serve.mode, serve.sessions, serve.duration_s) == ("closed", 5, 5.0)


@pytest.mark.parametrize("phase", ["compile", "boot", "serve"])
def test_an_oom_kill_fails_its_phase(tmp_path: Path, fakes: Fakes, phase: str):
    fakes.scope_reason = None
    fakes.oom_kill_at = phase
    entry = run(tmp_path, "memory.boot_512mb", limit_mb=128)
    assert entry["status"] == "failed"
    error = entry["error"]
    assert error.startswith(f"MemoryLimitExceeded: phase {phase} under MemoryMax=128M:")
    assert "oom_kill=1" in error
    assert "peak 300.0 MiB" in error
    assert "log tail:" in error


def test_a_boot_killed_before_ready_names_its_exit(tmp_path: Path, fakes: Fakes):
    fakes.scope_reason = None
    fakes.fail_start = True
    entry = run(tmp_path, "memory.boot_512mb", limit_mb=128)
    assert entry["status"] == "failed"
    error = entry["error"]
    assert error.startswith("MemoryLimitExceeded: phase boot under MemoryMax=128M:")
    assert "exited with code -9" in error
    assert "memory.events unreadable" in error
    assert error.endswith("log tail:\nStarting\nKilled")


def test_min_limit_bisects_to_the_smallest_passing_limit(
    tmp_path: Path, fakes: Fakes, monkeypatch: pytest.MonkeyPatch
):
    tried: list[int] = []

    def boot_and_serve(ctx, started, limit_mb):
        tried.append(limit_mb)
        if limit_mb < 288:
            msg = f"phase boot under MemoryMax={limit_mb}M: oom=1, oom_kill=1"
            raise memory.MemoryLimitExceeded(msg)
        return reading(), reading(memory_peak_bytes=250 * MIB), make_load_result()

    monkeypatch.setattr(memory, "boot_and_serve", boot_and_serve)
    fakes.scope_reason = None
    entry = run(tmp_path, "memory.boot.min_limit")
    assert entry["status"] == "ok", entry["error"]
    assert entry["metrics"]["min_limit"]["samples"]["A"] == [288 * MIB]
    assert tried[0] == 1024
    assert len(tried) <= 6
    (extra,) = entry["sample_extra"]
    assert [step["limit_mb"] for step in extra["steps"]] == tried
    assert {step["passed"] for step in extra["steps"] if step["limit_mb"] < 288} == {
        False
    }


def test_min_limit_fails_when_even_the_largest_limit_fails(
    tmp_path: Path, fakes: Fakes, monkeypatch: pytest.MonkeyPatch
):
    def boot_and_serve(ctx, started, limit_mb):
        msg = f"phase boot under MemoryMax={limit_mb}M: oom=0, oom_kill=1"
        raise memory.MemoryLimitExceeded(msg)

    monkeypatch.setattr(memory, "boot_and_serve", boot_and_serve)
    fakes.scope_reason = None
    entry = run(tmp_path, "memory.boot.min_limit")
    assert entry["status"] == "failed"
    assert "boot and serve fail even under 1024 MiB" in entry["error"]


def test_every_sample_names_its_memory_method(tmp_path: Path, fakes: Fakes):
    fakes.scope_reason = None
    fakes.load = leak_result(1000.0)
    fakes.answer_load = True
    for bench_id, params in (
        ("memory.compile.peak", {"command": "compile"}),
        ("memory.idle", {"idle_s": 0}),
        ("memory.per_session", {"max_sessions": 50, "expiry_s": 1}),
        ("memory.leak", {"events": 1000, "warmup_events": 0}),
        ("memory.boot_512mb", {}),
    ):
        entry = run(tmp_path / bench_id, bench_id, **params)
        assert entry["status"] == "ok", (bench_id, entry["error"])
        (extra,) = entry["sample_extra"]
        assert extra["memory_method"] == entry["dims"]["memory_method"], bench_id


def test_started_stops_what_starts_after_the_stop():
    started = memory._Started()
    stopped: list[str] = []
    started.add(lambda: stopped.append("first"))
    started.add(lambda: stopped.append("second"))
    started.stop()
    assert stopped == ["second", "first"]
    # A sample still running after conclude cannot leave anything behind.
    with pytest.raises(RuntimeError, match="the sample was stopped"):
        started.add(lambda: stopped.append("late"))
    assert stopped == ["second", "first", "late"]


def test_started_runs_every_stop_and_raises_after():
    started = memory._Started()
    stopped: list[str] = []

    def broken() -> None:
        msg = "stop failed"
        raise RuntimeError(msg)

    started.add(lambda: stopped.append("app"))
    started.add(broken)
    started.add(lambda: stopped.append("hold"))
    with pytest.raises(RuntimeError, match="stop failed"):
        started.stop()
    assert stopped == ["hold", "app"]


def test_largest_uss_is_the_worker(tree: tuple[int, int]):  # noqa: F811
    parent, _ = tree
    assert memory.largest_uss(parent) > 0
    assert memory.largest_uss(2**22 + 7) == 0
