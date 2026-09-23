"""Tests for reflex_bench.scheduler."""

from __future__ import annotations

import dataclasses
import os
import random
import shutil
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from reflex_bench import scheduler, store
from reflex_bench.context import BASE_ENV, Context
from reflex_bench.registry import Benchmark, Metric, ParamSet
from reflex_bench.scheduler import Planned, Policy, Scheduler

from .factories import WALL, make_subject


def _recorder(
    calls: list[str],
    sample: Callable[[Context], Any] | None = None,
    fail_in: str | None = None,
    **define: Any,
) -> Planned:
    """Build a planned instance whose hooks append their names to ``calls``.

    Args:
        calls: Receives the hook names in call order.
        sample: What ``sample`` does after recording; returns nothing by default.
        fail_in: A hook that raises after recording.
        **define: Overrides for :meth:`Benchmark.define`.

    Returns:
        The planned instance.
    """

    def hook(name: str) -> Callable[[Any, Context], Any]:
        def run(self: Any, ctx: Context) -> Any:
            calls.append(name)
            if name == fail_in:
                msg = f"{name} broke"
                raise RuntimeError(msg)
            if name == "sample" and sample is not None:
                return sample(ctx)
            return None

        return run

    hooks = ("setup_cache", "setup", "prepare", "sample", "conclude", "cleanup")
    recorder = type("Recorder", (), {name: hook(name) for name in hooks})
    arguments = {"id": "t.rec", "metrics": {"wall": WALL}, **define}
    bench = Benchmark.define(recorder, **arguments)
    return Planned(bench, bench.expand()[0])


@pytest.fixture
def fixed_timer(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every sample "takes" 0.25 s, so run counts do not depend on the machine.
    monkeypatch.setattr(scheduler, "_timed", lambda fn: (fn(), 250_000_000))


def _run(planned: Planned, tmp_path: Path, **policy: Any) -> dict[str, Any]:
    runner = Scheduler(make_subject(), Policy(**policy), home=tmp_path, seed=1)
    return dict(runner.run_one(planned))


def test_hook_order_with_warmup(tmp_path: Path):
    calls: list[str] = []
    entry = _run(_recorder(calls, warmup=1), tmp_path, runs=2)
    per_sample = ["prepare", "sample", "conclude"]
    assert calls == ["setup_cache", "setup", *per_sample * 3, "cleanup"]
    assert entry["status"] == "ok"
    assert [meta["warmup"] for meta in entry["sample_meta"]] == [True, False, False]


def test_warmup_samples_are_stored_but_excluded(tmp_path: Path, fixed_timer):
    values = iter([9.0, 8.0, 1.0, 2.0, 3.0])
    planned = _recorder([], sample=lambda ctx: {"wall": next(values)}, warmup=2)
    entry = _run(planned, tmp_path, runs=3)
    assert entry["metrics"]["wall"]["samples"] == {"A": [9.0, 8.0, 1.0, 2.0, 3.0]}
    summary = entry["metrics"]["wall"]["summary"]["A"]
    assert summary["n"] == 3
    assert summary["median"] == pytest.approx(2.0)
    assert entry["sample_extra"] == [None] * 5


def test_policy_warmup_overrides_the_benchmark(tmp_path: Path):
    calls: list[str] = []
    entry = _run(_recorder(calls, warmup=3), tmp_path, runs=1, warmup=0)
    assert calls.count("sample") == 1
    assert not entry["sample_meta"][0]["warmup"]


def test_measured_wall_time_fills_the_wall_metric(tmp_path: Path, fixed_timer):
    entry = _run(_recorder([]), tmp_path, runs=2)
    assert entry["metrics"]["wall"]["samples"]["A"] == [0.25, 0.25]
    assert [meta["duration_s"] for meta in entry["sample_meta"]] == [0.25, 0.25]


def test_run_count_rule():
    policy = Policy(min_runs=2, max_runs=5, min_time_s=1.0)
    assert policy.auto_runs(0.3) == 4
    assert policy.auto_runs(0.01) == 5
    assert policy.auto_runs(2.0) == 2
    assert policy.auto_runs(0.0) == 5


def test_run_count_rule_applies_after_the_first_timed_sample(
    tmp_path: Path, fixed_timer
):
    calls: list[str] = []
    entry = _run(_recorder(calls), tmp_path, min_runs=2, max_runs=10, min_time_s=1.0)
    # ceil(1.0 / 0.25) == 4 timed samples.
    assert calls.count("sample") == 4
    assert entry["metrics"]["wall"]["summary"]["A"]["n"] == 4


def test_exact_benchmarks_default_to_one_run(tmp_path: Path):
    exact = {"bytes": Metric(unit="B", direction="lower", assume="exact")}
    planned = _recorder([], sample=lambda ctx: {"bytes": 5}, metrics=exact)
    entry = _run(planned, tmp_path)
    assert entry["metrics"]["bytes"]["samples"]["A"] == [5.0]
    assert entry["metrics"]["bytes"]["warnings"] == []


def test_exact_metric_variance_warns(tmp_path: Path):
    values = iter([5, 6, 5])
    exact = {"bytes": Metric(unit="B", direction="lower", assume="exact")}
    planned = _recorder([], sample=lambda ctx: {"bytes": next(values)}, metrics=exact)
    entry = _run(planned, tmp_path, runs=3)
    assert entry["metrics"]["bytes"]["warnings"] == [
        "exact metric varied across 3 samples: 5 to 6 B"
    ]


def test_failure_still_runs_conclude_and_cleanup(tmp_path: Path):
    calls: list[str] = []
    counter = iter(range(10))

    def sample(ctx: Context) -> None:
        if next(counter) == 1:
            msg = "boom"
            raise RuntimeError(msg)

    entry = _run(_recorder(calls, sample=sample), tmp_path, runs=3)
    assert entry["status"] == "failed"
    assert entry["error"] == "RuntimeError: boom"
    assert "boom" in entry["traceback_tail"]
    assert len(entry["traceback_tail"].splitlines()) <= scheduler.TRACEBACK_LINES
    assert calls[-3:] == ["sample", "conclude", "cleanup"]
    # The sample taken before the failure is kept, without a summary.
    assert entry["metrics"]["wall"]["samples"]["A"] == [pytest.approx(0, abs=1)]
    assert entry["metrics"]["wall"]["summary"] == {}


@pytest.mark.parametrize("hook", ["setup_cache", "setup", "prepare", "conclude"])
def test_failure_in_any_hook_is_recorded(tmp_path: Path, hook: str):
    calls: list[str] = []
    entry = _run(_recorder(calls, fail_in=hook), tmp_path, runs=2)
    assert entry["status"] == "failed"
    assert entry["error"] == f"RuntimeError: {hook} broke"
    assert calls[-1] == "cleanup"


def test_failure_in_cleanup_fails_the_instance(tmp_path: Path):
    entry = _run(_recorder([], fail_in="cleanup"), tmp_path, runs=1)
    assert entry["status"] == "failed"
    assert entry["error"] == "RuntimeError: cleanup broke"


def test_teardown_errors_after_a_failure_are_kept_as_secondary(tmp_path: Path):
    def sample(ctx: Context) -> None:
        msg = "first"
        raise ValueError(msg)

    entry = _run(_recorder([], sample=sample, fail_in="conclude"), tmp_path, runs=1)
    assert entry["error"] == "ValueError: first"
    assert entry["traceback_tail"].endswith("also: RuntimeError: conclude broke")


def test_other_instances_continue_after_a_failure(tmp_path: Path):
    failing = _recorder([], fail_in="sample", id="t.fail")
    passing = _recorder([], id="t.pass")
    runner = Scheduler(make_subject(), Policy(runs=1), home=tmp_path, seed=1)
    assert [entry["status"] for entry in runner.run([failing, passing])] == [
        "failed",
        "ok",
    ]


def test_undeclared_metric_fails_the_instance(tmp_path: Path):
    entry = _run(_recorder([], sample=lambda ctx: {"wal": 1.0}), tmp_path, runs=1)
    assert entry["status"] == "failed"
    assert "undeclared metric(s) wal" in entry["error"]


def test_timeout_releases_the_sample_and_moves_on(tmp_path: Path):
    calls: list[str] = []
    release = threading.Event()

    def sample(ctx: Context) -> None:
        release.wait(30)

    class Releasing:
        """Blocks in sample until conclude releases it."""

        def sample(self, ctx: Context) -> None:
            calls.append("sample")
            sample(ctx)

        def conclude(self, ctx: Context) -> None:
            calls.append("conclude")
            release.set()

        def cleanup(self, ctx: Context) -> None:
            calls.append("cleanup")

    bench = Benchmark.define(
        Releasing, id="t.slow", metrics={"wall": WALL}, timeout=0.2
    )
    entry = _run(Planned(bench, ParamSet({})), tmp_path, runs=3)
    assert entry["status"] == "timeout"
    assert entry["error"] == "sample() exceeded the 0.2 s timeout"
    assert entry["traceback_tail"].startswith("hook was stuck at:")
    assert "release.wait(30)" in entry["traceback_tail"]
    assert calls == ["sample", "conclude", "cleanup"]


def test_policy_timeout_overrides_the_benchmark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(scheduler, "ABANDON_GRACE_S", 0.05)
    release = threading.Event()
    planned = _recorder([], sample=lambda ctx: release.wait(30))
    try:
        entry = _run(planned, tmp_path, runs=1, timeout_s=0.1)
    finally:
        release.set()
    assert entry["status"] == "timeout"
    assert entry["error"] == "sample() exceeded the 0.1 s timeout"


def test_a_hook_raising_timeout_error_is_a_failure(tmp_path: Path):
    def sample(ctx: Context) -> None:
        msg = "socket timed out"
        raise TimeoutError(msg)

    entry = _run(_recorder([], sample=sample), tmp_path, runs=1)
    assert entry["status"] == "failed"
    assert entry["error"] == "TimeoutError: socket timed out"


def test_sys_exit_in_a_hook_fails_the_instance(tmp_path: Path):
    entry = _run(_recorder([], sample=lambda ctx: sys.exit(3)), tmp_path, runs=1)
    assert entry["status"] == "failed"
    assert entry["error"] == "RuntimeError: hook raised SystemExit: 3"


def test_smoke_takes_one_sample_without_statistics(tmp_path: Path):
    calls: list[str] = []
    entry = _run(_recorder(calls, warmup=2), tmp_path, runs=5, smoke=True)
    assert calls.count("sample") == 1
    assert entry["metrics"]["wall"]["summary"] == {}
    assert not entry["sample_meta"][0]["warmup"]


def test_unsupported_subjects_skip_every_hook(tmp_path: Path):
    calls: list[str] = []
    entry = _run(_recorder(calls, min_version="99.0"), tmp_path)
    assert entry["status"] == "unsupported"
    assert entry["error"] == "requires reflex >= 99.0 (subject has 0.9.12)"
    assert calls == []
    assert entry["metrics"]["wall"]["samples"] == {}


def test_unsupported_reason():
    bench = Benchmark.define(
        type("B", (), {"sample": lambda self, ctx: None}),
        id="t.v",
        metrics={"wall": WALL},
        min_version="0.9.8",
    )
    assert scheduler.unsupported_reason(bench, make_subject("0.9.12")) is None
    assert scheduler.unsupported_reason(bench, make_subject("0.9.8")) is None
    assert scheduler.unsupported_reason(bench, make_subject("0.8.23")) == (
        "requires reflex >= 0.9.8 (subject has 0.8.23)"
    )
    assert "not installed" in (
        scheduler.unsupported_reason(bench, make_subject(None)) or ""
    )
    assert "cannot parse" in (
        scheduler.unsupported_reason(bench, make_subject("x.y")) or ""
    )


def test_setup_cache_runs_once_per_subject_and_params(tmp_path: Path):
    calls: list[str] = []
    planned = _recorder(calls)
    runner = Scheduler(make_subject(), Policy(runs=1), home=tmp_path, seed=1)
    runner.run_one(planned)
    runner.run_one(planned)
    assert calls.count("setup_cache") == 1
    assert calls.count("setup") == 2


def test_context(tmp_path: Path):
    seen: list[Context] = []

    def sample(ctx: Context) -> None:
        assert ctx.workdir.is_dir()
        seen.append(ctx)

    planned = _recorder(
        [], sample=sample, params={"n": [7]}, hidden_params={"shift": 2.0}
    )
    entry = _run(planned, tmp_path / "home", runs=1)
    (ctx,) = seen
    assert ctx.params == {"n": 7, "shift": 2.0}
    assert ctx.arm == "A"
    assert all(ctx.env[key] == value for key, value in BASE_ENV.items())
    assert ctx.cache_dir == store.cache_dir(
        tmp_path / "home", ctx.subject.identity, "t.rec", {"n": 7}
    )
    assert ctx.cache_dir.is_dir()
    assert not ctx.workdir.exists()
    assert entry["params"] == {"n": 7}
    assert entry["hidden_params"] == {"shift": 2.0}


def test_context_errors_are_failures_not_crashes(tmp_path: Path):
    home = tmp_path / "not-a-directory"
    home.write_text("x", encoding="utf-8")
    calls: list[str] = []
    runner = Scheduler(make_subject(), Policy(runs=1), home=home, seed=1)
    entry = runner.run_one(_recorder(calls))
    assert entry["status"] == "failed"
    assert calls == []


def test_keep_leaves_the_work_directory(tmp_path: Path):
    runner = Scheduler(make_subject(), Policy(runs=1), home=tmp_path, seed=1, keep=True)
    runner.run_one(_recorder([]))
    (kept,) = runner.kept
    assert kept.is_dir()


def test_rng_is_seeded_per_instance(tmp_path: Path):
    def draws(seed: int) -> list[float]:
        planned = _recorder([], sample=lambda ctx: {"wall": ctx.rng.random()})
        runner = Scheduler(make_subject(), Policy(runs=3), home=tmp_path, seed=seed)
        return runner.run_one(planned)["metrics"]["wall"]["samples"]["A"]

    assert draws(1) == draws(1)
    assert draws(1) != draws(2)


def test_events(tmp_path: Path):
    events: list[dict[str, Any]] = []
    runner = Scheduler(
        make_subject(), Policy(runs=2), home=tmp_path, seed=1, on_event=events.append
    )
    runner.run_one(_recorder([], warmup=1))
    assert [event["event"] for event in events] == [
        "benchmark_start",
        "sample",
        "sample",
        "sample",
        "benchmark_end",
    ]
    assert [event["warmup"] for event in events[1:4]] == [True, False, False]
    assert events[-1]["status"] == "ok"
    assert events[-1]["n"] == 2


def test_policy_validation():
    with pytest.raises(ValueError, match="max-runs must be >= min-runs"):
        Policy(min_runs=5, max_runs=2)
    doc = Policy(fail_on="regression", fail_on_inconclusive=True).to_doc()
    assert (doc["correction"], doc["fail_on"], doc["fail_on_inconclusive"]) == (
        "holm",
        "regression",
        True,
    )


def test_derive_seed_is_stable():
    assert scheduler.derive_seed(1, "a", "b") == scheduler.derive_seed(1, "a", "b")
    assert scheduler.derive_seed(1, "a", "b") != scheduler.derive_seed(1, "a", "c")


def test_interrupt_runs_conclude_on_a_fresh_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    calls: list[str] = []
    release = threading.Event()
    waits = 0
    real_wait = scheduler.concurrent.futures.wait

    def interrupting_wait(futures: Any, timeout: float | None = None) -> Any:
        nonlocal waits
        waits += 1
        # setup_cache, setup, prepare, then Ctrl-C while sample() blocks.
        if waits == 4:
            raise KeyboardInterrupt
        return real_wait(futures, timeout=timeout)

    class Releasing:
        """Blocks in sample until conclude releases it."""

        def sample(self, ctx: Context) -> None:
            calls.append("sample")
            release.wait(30)

        def conclude(self, ctx: Context) -> None:
            calls.append("conclude")
            release.set()

        def cleanup(self, ctx: Context) -> None:
            calls.append("cleanup")

    bench = Benchmark.define(Releasing, id="t.int", metrics={"wall": WALL}, timeout=30)
    monkeypatch.setattr(scheduler.concurrent.futures, "wait", interrupting_wait)
    started = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        _run(Planned(bench, ParamSet({})), tmp_path, runs=1)
    assert time.monotonic() - started < 5
    assert release.is_set()
    assert calls[-2:] == ["conclude", "cleanup"]


def test_a_timed_out_hook_finishes_before_its_work_directory_is_removed(
    tmp_path: Path,
):
    finished = threading.Event()
    workdirs: list[Path] = []

    def sample(ctx: Context) -> None:
        workdirs.append(ctx.workdir)
        time.sleep(0.3)
        finished.set()

    entry = _run(_recorder([], sample=sample), tmp_path, runs=1, timeout_s=0.05)
    assert entry["status"] == "timeout"
    assert finished.is_set()
    assert not workdirs[0].exists()


def test_a_stuck_hook_keeps_the_work_directory_and_skips_other_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(scheduler, "ABANDON_GRACE_S", 0.05)
    release = threading.Event()
    calls: list[str] = []

    class Stuck:
        """setup_cache() never returns for p=1."""

        def setup_cache(self, ctx: Context) -> None:
            calls.append(f"setup_cache {ctx.params['p']}")
            if ctx.params["p"] == 1:
                release.wait(30)

        def sample(self, ctx: Context) -> None:
            calls.append("sample")

    bench = Benchmark.define(
        Stuck,
        id="t.stuck",
        metrics={"wall": WALL},
        params={"p": [1, 2]},
        setup_timeout=0.05,
    )
    runner = Scheduler(make_subject(), Policy(runs=1), home=tmp_path, seed=1)
    try:
        first, second = runner.run(scheduler.plan([bench]))
    finally:
        release.set()
    assert first["status"] == "timeout"
    assert "setup_cache() of t.stuck[p=1] was still running" in (
        first["traceback_tail"] or ""
    )
    (kept,) = runner.kept
    assert kept.is_dir()
    assert second["status"] == "skipped"
    assert second["error"] == (
        "setup_cache() of t.stuck[p=1] was still running after teardown"
    )
    assert calls == ["setup_cache 1"]


def test_setup_cache_gets_one_cache_dir_per_param_set(tmp_path: Path):
    dirs: dict[int, Path] = {}

    class Caching:
        """Records the cache directory setup_cache() sees."""

        def setup_cache(self, ctx: Context) -> None:
            dirs[ctx.params["p"]] = ctx.cache_dir

        def sample(self, ctx: Context) -> None:
            pass

    bench = Benchmark.define(
        Caching, id="t.cache", metrics={"wall": WALL}, params={"p": [1, 2]}
    )
    runner = Scheduler(make_subject(), Policy(runs=1), home=tmp_path, seed=1)
    runner.run(scheduler.plan([bench]))
    assert dirs[1] != dirs[2]
    assert dirs[1].parent == dirs[2].parent


def test_make_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/local/bin", "/usr/bin"]))
    planned = _recorder([], params={"n": [7]}, hidden_params={"shift": 2.0})
    subject = dataclasses.replace(
        make_subject(), python=tmp_path / "venv" / "bin" / "python"
    )
    ctx = scheduler.make_context(subject, planned, home=tmp_path, seed=3, arm="B")
    try:
        assert ctx.subject is subject
        assert ctx.params == {"n": 7, "shift": 2.0}
        assert ctx.arm == "B"
        assert ctx.workdir.is_dir()
        assert ctx.cache_dir.is_dir()
        assert ctx.cache_dir == store.cache_dir(
            tmp_path, subject.identity, "t.rec", {"n": 7}
        )
        assert all(ctx.env[key] == value for key, value in BASE_ENV.items())
        # Commands the subject starts by name come from its own environment.
        assert ctx.env["PATH"].split(os.pathsep) == [
            str(tmp_path / "venv" / "bin"),
            "/usr/local/bin",
            "/usr/bin",
        ]
        expected = random.Random(scheduler.derive_seed(3, "t.rec[n=7]", "B"))
        assert ctx.rng.random() == expected.random()
    finally:
        shutil.rmtree(ctx.workdir)


def test_open_sessions_alternate_samples(tmp_path: Path):
    calls: list[str] = []
    planned = _recorder(calls)
    entry = scheduler.new_entry(planned)
    runner = Scheduler(make_subject(), Policy(), home=tmp_path, seed=1)
    with (
        runner.open(planned, entry, arm="A") as a,
        runner.open(planned, entry, arm="B") as b,
    ):
        assert a.ctx is not None
        assert b.ctx is not None
        assert a.ctx.arm == "A"
        assert b.ctx.arm == "B"
        for round_, order in ((0, 0), (0, 1), (1, 0), (1, 1)):
            session = (a, b, b, a)[2 * round_ + order]
            taken = session.sample_once(round=round_, order=order, warmup=round_ == 0)
            assert taken is not None
    assert calls.count("setup") == 2
    assert calls.count("cleanup") == 2
    assert entry["status"] == "ok"
    assert [
        (meta["arm"], meta["round"], meta["order"], meta["warmup"])
        for meta in entry["sample_meta"]
    ] == [
        ("A", 0, 0, True),
        ("B", 0, 1, True),
        ("B", 1, 0, False),
        ("A", 1, 1, False),
    ]
    assert {arm: len(v) for arm, v in entry["metrics"]["wall"]["samples"].items()} == {
        "A": 2,
        "B": 2,
    }


def test_a_failed_session_takes_no_samples_and_records_the_failure(tmp_path: Path):
    calls: list[str] = []
    planned = _recorder(calls, fail_in="setup")
    entry = scheduler.new_entry(planned)
    runner = Scheduler(make_subject(), Policy(), home=tmp_path, seed=1)
    with runner.open(planned, entry) as session:
        assert session.sample_once(round=0, order=0, warmup=False) is None
    assert "sample" not in calls
    assert calls[-1] == "cleanup"
    assert entry["status"] == "failed"
    assert entry["error"] == "RuntimeError: setup broke"


def test_failures_record_the_failing_arm(tmp_path: Path):
    failed = _run(_recorder([], fail_in="sample"), tmp_path, runs=1)
    assert failed["failed_arms"] == ["A"]
    assert "failed_arms" not in _run(_recorder([]), tmp_path, runs=1)


def test_skip_reason(tmp_path: Path):
    runner = Scheduler(make_subject("0.8.23"), Policy(), home=tmp_path, seed=1)
    assert runner.skip_reason(_recorder([])) is None
    assert runner.skip_reason(_recorder([], min_version="0.9.0")) == (
        "unsupported",
        "requires reflex >= 0.9.0 (subject has 0.8.23)",
    )
