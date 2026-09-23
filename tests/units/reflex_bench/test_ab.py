"""Tests for reflex_bench.ab."""

from __future__ import annotations

import random
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from reflex_bench import ab, scheduler
from reflex_bench.context import Context, Subject
from reflex_bench.registry import Benchmark
from reflex_bench.scheduler import Planned, Policy, Scheduler
from reflex_bench.schema import BenchmarkDoc

from .factories import WALL, make_entry, make_subject

ABBA = [("A", "B"), ("B", "A"), ("A", "B"), ("B", "A"), ("A", "B")]


def _planned(
    sample: Callable[[Context], Any] | None = None,
    calls: list[str] | None = None,
    **define: Any,
) -> Planned:
    """Build a planned instance whose hooks record ``<hook> <arm>`` in ``calls``.

    Args:
        sample: What ``sample`` does after recording; returns nothing by default.
        calls: Receives the hook calls in order.
        **define: Overrides for :meth:`Benchmark.define`.

    Returns:
        The planned instance.
    """
    record = [] if calls is None else calls

    class Recorder:
        """Records its hook calls."""

        def setup(self, ctx: Context) -> None:
            record.append(f"setup {ctx.arm}")

        def sample(self, ctx: Context) -> Any:
            record.append(f"sample {ctx.arm}")
            return None if sample is None else sample(ctx)

        def cleanup(self, ctx: Context) -> None:
            record.append(f"cleanup {ctx.arm}")

    bench = Benchmark.define(
        Recorder, **{"id": "t.ab", "metrics": {"wall": WALL}, **define}
    )
    return Planned(bench, bench.expand()[0])


def _schedulers(
    tmp_path: Path,
    base: Subject | None = None,
    head: Subject | None = None,
    **policy: Any,
) -> tuple[Scheduler, Scheduler]:
    shared = Policy(**{"runs": 3, **policy})
    return (
        Scheduler(base or make_subject(), shared, home=tmp_path, seed=1),
        Scheduler(head or make_subject(), shared, home=tmp_path, seed=1),
    )


def _run(
    planned: Sequence[Planned], schedulers: tuple[Scheduler, Scheduler], **kwargs: Any
) -> list[BenchmarkDoc]:
    kwargs.setdefault("order", "abba")
    return ab.run(planned, *schedulers, **kwargs)


def _arms(entry: BenchmarkDoc) -> list[tuple[str, int, int, bool]]:
    return [
        (meta["arm"], meta["round"], meta["order"], meta["warmup"])
        for meta in entry["sample_meta"]
    ]


@pytest.mark.parametrize("rounds", [1, 2, 3, 4, 5])
def test_abba_orders(rounds: int):
    assert ab.round_orders(rounds, "abba", random.Random(0)) == ABBA[:rounds]


def test_random_orders_are_reproducible():
    first = ab.round_orders(40, "random", random.Random(7))
    assert first == ab.round_orders(40, "random", random.Random(7))
    assert first != ab.round_orders(40, "random", random.Random(8))
    assert set(first) == {("A", "B"), ("B", "A")}


def test_two_sessions_fill_one_entry(tmp_path: Path):
    calls: list[str] = []
    planned = _planned(
        lambda ctx: {"wall": 1.2 if ctx.subject.reflex_version == "0.9.13" else 1.0},
        calls,
        warmup=1,
    )
    schedulers = _schedulers(tmp_path, head=make_subject("0.9.13"))
    (entry,) = _run([planned], schedulers)
    assert entry["status"] == "ok"
    assert _arms(entry) == [
        ("A", 0, 0, True),
        ("B", 0, 1, True),
        ("A", 0, 0, False),
        ("B", 0, 1, False),
        ("B", 1, 0, False),
        ("A", 1, 1, False),
        ("A", 2, 0, False),
        ("B", 2, 1, False),
    ]
    assert calls[:2] == ["setup A", "setup B"]
    assert sorted(calls[-2:]) == ["cleanup A", "cleanup B"]
    wall = entry["metrics"]["wall"]
    assert wall["samples"] == {"A": [1.0] * 4, "B": [1.2] * 4}
    # finalize() summarizes each arm's timed samples.
    assert {arm: (s["n"], s["median"]) for arm, s in wall["summary"].items()} == {
        "A": (3, 1.0),
        "B": (3, 1.2),
    }


def test_random_order_is_seeded_per_instance(tmp_path: Path):
    def orders(seed: int) -> list[tuple[str, int, int, bool]]:
        base, head = _schedulers(tmp_path, runs=12)
        base.seed = head.seed = seed
        return _arms(_run([_planned()], (base, head), order="random")[0])

    first = orders(5)
    assert first == orders(5)
    assert first != orders(6)
    assert [arm for arm, _, order, _ in first if order == 0] != ["A"] * 12


def test_a_failure_in_either_arm_stops_the_instance(tmp_path: Path):
    calls: list[str] = []

    def sample(ctx: Context) -> None:
        if ctx.arm == "B" and calls.count("sample B") == 2:
            msg = "head broke"
            raise RuntimeError(msg)

    (entry,) = _run([_planned(sample, calls)], _schedulers(tmp_path, runs=5))
    assert entry["status"] == "failed"
    assert entry["error"] == "RuntimeError: head broke"
    assert entry.get("failed_arms") == ["B"]
    # Round 1 starts with B, which fails: nothing runs after it.
    assert [arm for arm, *_ in _arms(entry)] == ["A", "B"]
    assert calls.count("sample A") == 1
    assert calls.count("cleanup A") == calls.count("cleanup B") == 1
    assert entry["metrics"]["wall"]["summary"] == {}


def test_a_failed_setup_takes_no_samples_in_either_arm(tmp_path: Path):
    calls: list[str] = []

    class Broken:
        """Fails to set up in arm A."""

        def setup(self, ctx: Context) -> None:
            if ctx.arm == "A":
                msg = "base broke"
                raise RuntimeError(msg)

        def sample(self, ctx: Context) -> None:
            calls.append(f"sample {ctx.arm}")

    bench = Benchmark.define(Broken, id="t.broken", metrics={"wall": WALL})
    planned = Planned(bench, bench.expand()[0])
    (entry,) = _run([planned], _schedulers(tmp_path))
    assert (entry["status"], entry["error"]) == ("failed", "RuntimeError: base broke")
    assert entry.get("failed_arms") == ["A"]
    assert calls == []


def test_an_arm_too_old_for_the_benchmark_skips_the_instance(tmp_path: Path):
    calls: list[str] = []
    planned = _planned(calls=calls, min_version="0.9.0")
    schedulers = _schedulers(tmp_path, head=make_subject("0.8.23"))
    (entry,) = _run([planned], schedulers)
    assert entry["status"] == "unsupported"
    assert entry["error"] == "B: requires reflex >= 0.9.0 (subject has 0.8.23)"
    assert calls == []


def test_a_stuck_hook_in_one_arm_skips_the_remaining_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(scheduler, "ABANDON_GRACE_S", 0.05)
    release = threading.Event()

    class Stuck:
        """setup() never returns in arm B for p=1."""

        def setup(self, ctx: Context) -> None:
            if ctx.arm == "B" and ctx.params["p"] == 1:
                release.wait(30)

        def sample(self, ctx: Context) -> None:
            pass

    bench = Benchmark.define(
        Stuck,
        id="t.stuck",
        metrics={"wall": WALL},
        params={"p": [1, 2]},
        setup_timeout=0.05,
    )
    try:
        first, second = _run(scheduler.plan([bench]), _schedulers(tmp_path))
    finally:
        release.set()
    assert first["status"] == "timeout"
    assert first.get("failed_arms") == ["B"]
    assert second["status"] == "skipped"
    assert second["error"] == (
        "B: setup() of t.stuck[p=1] was still running after teardown"
    )


def test_events(tmp_path: Path):
    events: list[dict[str, Any]] = []
    _run(
        [_planned(warmup=1)],
        _schedulers(tmp_path, runs=2),
        on_event=events.append,
    )
    assert [event["event"] for event in events] == [
        "benchmark_start",
        *["sample"] * 6,
        "benchmark_end",
    ]
    samples = [event for event in events if event["event"] == "sample"]
    assert [(e["arm"], e["warmup"], e["timed"], e["target"]) for e in samples] == [
        ("A", True, 0, 4),
        ("B", True, 0, 4),
        ("A", False, 1, 4),
        ("B", False, 2, 4),
        ("B", False, 3, 4),
        ("A", False, 4, 4),
    ]
    assert [event["index"] for event in samples] == list(range(6))
    assert (events[-1]["status"], events[-1]["n"]) == ("ok", 4)


def test_run_needs_a_fixed_round_count(tmp_path: Path):
    with pytest.raises(ValueError, match="fixed number of rounds"):
        _run([_planned()], _schedulers(tmp_path, runs=None))


def _entry(samples: Mapping[str, Sequence[float]]) -> BenchmarkDoc:
    """Build an entry whose arms' samples alternate, one warmup per arm first.

    Args:
        samples: The timed samples of each arm.

    Returns:
        The entry.
    """
    entry = make_entry("t.drift", {"value": (WALL, [])})
    rounds = max(len(values) for values in samples.values())
    for index in range(-1, rounds):
        for order, (arm, values) in enumerate(samples.items()):
            if index >= len(values):
                continue
            value = values[0] if index < 0 else values[index]
            entry["metrics"]["value"]["samples"].setdefault(arm, []).append(value)
            entry["sample_meta"].append({
                "arm": arm,
                "round": max(index, 0),
                "order": order,
                "started_at": "2026-09-23T10:15:00.000Z",
                "warmup": index < 0,
                "duration_s": 0.01,
            })
            entry["sample_extra"].append(None)
    return entry


def test_drift_warnings_flag_a_trend_in_one_arm():
    rising = [1.0 + 0.01 * i for i in range(8)]
    falling = list(reversed(rising))
    flat = [1.0, 1.02, 0.99, 1.01, 1.0, 0.98, 1.02, 0.99]
    entry = _entry({"A": rising, "B": flat})
    ab.drift_warnings(entry)
    # Exact p of a perfect order of 8: 2 / 8! permutations.
    assert entry["metrics"]["value"]["warnings"] == [
        "drift: value trends with time in arm A (rho=1.00, p=5e-05)"
    ]
    entry = _entry({"A": flat, "B": falling})
    ab.drift_warnings(entry)
    assert entry["metrics"]["value"]["warnings"] == [
        "drift: value trends with time in arm B (rho=-1.00, p=5e-05)"
    ]


def test_drift_needs_a_significant_and_strong_trend():
    # A perfect order of 5 has p = 2 / 5! = 0.017, above 0.01.
    entry = _entry({"A": [1.0 + 0.01 * i for i in range(5)], "B": [1.0] * 5})
    ab.drift_warnings(entry)
    assert entry["metrics"]["value"]["warnings"] == []
    # rho = 0.78 over 10 samples: p = 0.0105, just above 0.01.
    moderate = [2.0, 1.0, 4.0, 3.0, 8.0, 5.0, 10.0, 6.0, 9.0, 7.0]
    entry = _entry({"A": moderate, "B": [1.0] * 10})
    ab.drift_warnings(entry)
    assert entry["metrics"]["value"]["warnings"] == []
    # rho = 0.33 over 200 samples: p = 4e-06 but a weak trend.
    rng = random.Random(1)
    weak = [index + rng.gauss(0, 200) for index in range(200)]
    entry = _entry({"A": weak, "B": [1.0] * 200})
    ab.drift_warnings(entry)
    assert entry["metrics"]["value"]["warnings"] == []


def test_drift_rarely_warns_without_a_trend():
    rng = random.Random(7)
    warned = 0
    for _ in range(1000):
        entry = _entry({"A": [rng.random() for _ in range(10)], "B": [1.0] * 10})
        ab.drift_warnings(entry)
        warned += bool(entry["metrics"]["value"]["warnings"])
    assert warned < 20


def test_drift_is_checked_after_finalize(tmp_path: Path):
    values = iter(range(100))
    planned = _planned(lambda ctx: {"wall": 1.0 + 0.01 * next(values)})
    (entry,) = _run([planned], _schedulers(tmp_path, runs=8))
    assert entry["metrics"]["wall"]["warnings"] == [
        "drift: wall trends with time in arm A (rho=1.00, p=5e-05)",
        "drift: wall trends with time in arm B (rho=1.00, p=5e-05)",
    ]
