"""Interleaved A/B runs: two subjects measured in alternation on one machine.

Timing arm A fully and then arm B lets machine drift (thermal state,
background load, caches) bias the comparison. Here both arms' sessions of an
instance are open at once and their samples alternate: warmups go A, B, A, B,
then the timed rounds go AB, BA, AB, ... (ABBA) or in a seeded random order per
round, so drift hits both arms alike. Both arms fill one result entry, which is
then compared arm against arm. A benchmark that keeps a heavy process alive
between samples therefore runs two of them at once, one per arm.
"""

from __future__ import annotations

import contextlib
import random
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Literal, get_args

from reflex_bench import stats
from reflex_bench.scheduler import (
    Event,
    Planned,
    Scheduler,
    Session,
    derive_seed,
    finalize,
    new_entry,
)
from reflex_bench.schema import BenchmarkDoc, timed_values

Order = Literal["abba", "random"]
ORDERS: tuple[Order, ...] = get_args(Order)
DRIFT_P = 0.01
DRIFT_RHO = 0.5


def round_orders(
    rounds: int, order: Order, rng: random.Random
) -> list[tuple[str, str]]:
    """Decide which arm samples first in each timed round.

    Args:
        rounds: The number of rounds.
        order: ``abba`` alternates AB and BA; ``random`` shuffles each round.
        rng: The generator of ``random`` orders.

    Returns:
        The two arms of each round, in sampling order.
    """
    if order == "abba":
        return [("A", "B") if index % 2 == 0 else ("B", "A") for index in range(rounds)]
    # Shuffling two arms is a coin flip.
    return [("A", "B") if rng.random() < 0.5 else ("B", "A") for _ in range(rounds)]


def drift_warnings(entry: BenchmarkDoc) -> None:
    """Warn about metrics whose timed samples trend with time in an arm.

    Spearman's rho between an arm's values of a metric and their positions in
    the whole interleaved sequence: a significant (``p < 0.01``) and strong
    (``|rho| >= 0.5``) trend suggests the machine (or the benchmark's state)
    drifted during the run.

    Args:
        entry: The benchmark entry; warnings are appended to its metrics.
    """
    positions: dict[str, list[int]] = {}
    for position, meta in enumerate(entry["sample_meta"]):
        if not meta["warmup"]:
            positions.setdefault(meta["arm"], []).append(position)
    for name, metric in entry["metrics"].items():
        for arm, where in sorted(positions.items()):
            rho = stats.spearman(timed_values(entry, name, arm), where)
            if abs(rho) < DRIFT_RHO:
                continue
            p = stats.spearman_p(rho, len(where))
            if p < DRIFT_P:
                metric["warnings"].append(
                    f"drift: {name} trends with time in arm {arm}"
                    f" (rho={rho:.2f}, p={p:.2g})"
                )


def _interleave(
    planned: Planned,
    sessions: Mapping[str, Session],
    orders: Sequence[tuple[str, str]],
    warmup: int,
    emit: Callable[[Event], None],
) -> None:
    """Take the warmup and timed samples of both arms until one arm fails.

    Args:
        planned: The instance.
        sessions: The open session of each arm.
        orders: The arms of each timed round, in sampling order.
        warmup: Untimed samples per arm.
        emit: Receives a ``sample`` event per sample.
    """
    steps = [
        *((index, ("A", "B"), True) for index in range(warmup)),
        *((index, arms, False) for index, arms in enumerate(orders)),
    ]
    target = 2 * len(orders)
    taken = timed = 0
    for round_, arms, is_warmup in steps:
        for position, arm in enumerate(arms):
            sample = sessions[arm].sample_once(
                round=round_, order=position, warmup=is_warmup
            )
            if sample is None:
                return
            result, duration = sample
            if not is_warmup:
                timed += 1
            emit({
                "event": "sample",
                "id": planned.name,
                "index": taken,
                "arm": arm,
                "round": round_,
                "order": position,
                "warmup": is_warmup,
                "timed": timed,
                "target": target,
                "duration_s": duration,
                "values": dict(result.values),
            })
            taken += 1


def _run_one(
    planned: Planned,
    schedulers: Mapping[str, Scheduler],
    orders: Sequence[tuple[str, str]],
    emit: Callable[[Event], None],
    index: int,
    total: int,
) -> BenchmarkDoc:
    """Measure one instance on both arms.

    Args:
        planned: The instance.
        schedulers: The scheduler of each arm.
        orders: The arms of each timed round, in sampling order.
        emit: Receives progress events.
        index: The instance's position in the run.
        total: The number of instances in the run.

    Returns:
        The entry holding both arms' samples, summaries and drift warnings.
    """
    policy = schedulers["A"].policy
    entry = new_entry(planned)
    emit({
        "event": "benchmark_start",
        "id": planned.name,
        "index": index,
        "total": total,
    })
    started = time.perf_counter()
    skipped = next(
        (
            (arm, skip)
            for arm, scheduler in schedulers.items()
            if (skip := scheduler.skip_reason(planned)) is not None
        ),
        None,
    )
    if skipped is not None:
        arm, (status, reason) = skipped
        entry["status"], entry["error"] = status, f"{arm}: {reason}"
    else:
        bench = planned.benchmark
        with contextlib.ExitStack() as stack:
            sessions = {
                arm: stack.enter_context(scheduler.open(planned, entry, arm=arm))
                for arm, scheduler in schedulers.items()
            }
            _interleave(
                planned,
                sessions,
                orders,
                bench.warmup if policy.warmup is None else policy.warmup,
                emit,
            )
        if entry["status"] == "ok":
            finalize(entry, policy.confidence)
            drift_warnings(entry)
    emit({
        "event": "benchmark_end",
        "id": planned.name,
        "index": index,
        "total": total,
        "status": entry["status"],
        "error": entry["error"],
        "n": sum(not meta["warmup"] for meta in entry["sample_meta"]),
        "elapsed_s": round(time.perf_counter() - started, 6),
    })
    return entry


def run(
    planned: Sequence[Planned],
    base: Scheduler,
    head: Scheduler,
    *,
    order: Order = "abba",
    on_event: Callable[[Event], None] | None = None,
) -> list[BenchmarkDoc]:
    """Measure every instance on two subjects, interleaving their samples.

    For each instance both sessions are opened (setup of A, then of B), the
    warmup samples alternate A, B, and each timed round samples both arms in
    the round's order. A failure in either arm ends the instance; its entry
    records the failure and the failing arms.

    Args:
        planned: The instances.
        base: Measures arm A, the reference. Its policy, whose ``runs`` is the
            fixed number of rounds, and its seed apply to both arms.
        head: Measures arm B, the arm judged.
        order: The order of the arms within each timed round.
        on_event: Receives progress events (``benchmark_start``, ``sample`` with
            its ``arm``, ``benchmark_end``).

    Returns:
        One entry per instance, with both arms' samples and per-arm summaries.

    Raises:
        ValueError: When the policy has no fixed number of rounds.
    """
    rounds = base.policy.runs
    if rounds is None:
        msg = "an A/B run needs a fixed number of rounds (Policy.runs)"
        raise ValueError(msg)
    schedulers = {"A": base, "B": head}
    emit = on_event or (lambda event: None)
    return [
        _run_one(
            item,
            schedulers,
            # Each instance draws its own order, whatever else runs.
            round_orders(
                rounds, order, random.Random(derive_seed(base.seed, item.name, "order"))
            ),
            emit,
            index,
            len(planned),
        )
        for index, item in enumerate(planned)
    ]
