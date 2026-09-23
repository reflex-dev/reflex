"""Builders for reflex-bench result documents used across the tests."""

from __future__ import annotations

import logging
import random
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from reflex_bench.context import Context, Subject
from reflex_bench.drivers.events import LoadResult
from reflex_bench.registry import Metric
from reflex_bench.scheduler import Policy, finalize
from reflex_bench.schema import SCHEMA_ID, BenchmarkDoc, MachineDoc, ResultDoc

VERSION = "sha256:" + "0" * 64
WALL = Metric(unit="s", direction="lower")


def make_subject(reflex_version: str | None = "0.9.12") -> Subject:
    """Build a subject that does not depend on the checkout.

    Args:
        reflex_version: The reflex version to report.

    Returns:
        The subject.
    """
    return Subject(
        spec="workspace",
        source="workspace",
        python=Path(sys.executable),
        reflex_version=reflex_version,
        commit="258d66c2a1b3c4d5e6f708192a3b4c5d6e7f8091",
        dirty=True,
        python_version="3.12.8",
    )


def make_context(tmp_path: Path, params: Mapping[str, Any] | None = None) -> Context:
    """Build a context for calling hooks directly.

    Args:
        tmp_path: A scratch directory for the work and cache directories.
        params: The parameters hooks see.

    Returns:
        The context.
    """
    return Context(
        subject=make_subject(),
        params=dict(params or {}),
        workdir=tmp_path,
        cache_dir=tmp_path,
        env={},
        rng=random.Random(0),
        log=logging.getLogger("reflex_bench.test"),
    )


def make_machine(profile_id: str = "test-profile", **changes: Any) -> MachineDoc:
    """Build a machine entry.

    Args:
        profile_id: The machine profile id.
        **changes: Fields to override.

    Returns:
        The machine entry.
    """
    machine: MachineDoc = {
        "profile_id": profile_id,
        "os": "Linux",
        "kernel": "7.0.0-31-generic",
        "arch": "x86_64",
        "cpu_model": "AMD Ryzen 9 7950X 16-Core Processor",
        "cpu_count": 32,
        "ram_bytes": 67_108_864_000,
        "governor": "powersave",
        "turbo": True,
        "load_avg_1m": 0.4,
        "ac_power": None,
        "cgroup_v2": True,
        "container": False,
        "virtualized": False,
        "tools": {"bun": True, "node": True, "chromium": False},
    }
    machine.update(changes)  # pyright: ignore[reportCallIssue, reportArgumentType]
    return machine


def make_entry(
    bench_id: str,
    metrics: Mapping[str, tuple[Metric, Sequence[float]]],
    *,
    params: Mapping[str, Any] | None = None,
    warmup: int = 0,
    status: str = "ok",
    error: str | None = None,
    version: str = VERSION,
    confidence: float = 0.95,
) -> BenchmarkDoc:
    """Build a benchmark entry from raw samples, with derived summaries.

    Args:
        bench_id: The benchmark id.
        metrics: Metric name to its declaration and its samples (warmups first).
        params: The visible parameters.
        warmup: How many of the leading samples are warmups.
        status: The entry status.
        error: The error message.
        version: The benchmark version.
        confidence: The confidence level of the summaries.

    Returns:
        The entry.
    """
    count = max((len(values) for _, values in metrics.values()), default=0)
    entry: BenchmarkDoc = {
        "id": bench_id,
        "params": dict(params or {}),
        "kind": "time",
        "version": version,
        "status": status,  # pyright: ignore[reportAssignmentType]
        "error": error,
        "traceback_tail": None,
        "dims": {},
        "metrics": {
            name: {
                "unit": metric.unit,
                "direction": metric.direction,
                "assume": metric.assume,
                "samples": {"A": [float(v) for v in values]} if values else {},
                "summary": {},
                "comparison": None,
                "warnings": [],
            }
            for name, (metric, values) in metrics.items()
        },
        "sample_meta": [
            {
                "arm": "A",
                "round": 0,
                "order": 0,
                "started_at": "2026-09-23T10:15:00.000Z",
                "warmup": index < warmup,
                "duration_s": 0.01,
            }
            for index in range(count)
        ],
        "sample_extra": [None] * count,
    }
    if status == "ok":
        finalize(entry, confidence)
    return entry


def make_ab_entry(
    bench_id: str,
    metrics: Mapping[str, tuple[Metric, Mapping[str, Sequence[float]]]],
    *,
    status: str = "ok",
    error: str | None = None,
    failed_arms: Sequence[str] | None = None,
) -> BenchmarkDoc:
    """Build an entry of an interleaved run: arms alternate, round by round.

    Args:
        bench_id: The benchmark id.
        metrics: Metric name to its declaration and each arm's timed samples; all
            metrics have the same arms and sample counts.
        status: The entry status.
        error: The error message.
        failed_arms: The arms whose hooks failed.

    Returns:
        The entry, summarized when its status is ``ok``.
    """
    entry = make_entry(
        bench_id,
        {name: (metric, []) for name, (metric, _) in metrics.items()},
        status=status,
        error=error,
    )
    _, arms = next(iter(metrics.values()))
    for index in range(max(len(values) for values in arms.values())):
        for order, (arm, values) in enumerate(arms.items()):
            if index >= len(values):
                continue
            for name, (_, samples) in metrics.items():
                entry["metrics"][name]["samples"].setdefault(arm, []).append(
                    float(samples[arm][index])
                )
            entry["sample_meta"].append({
                "arm": arm,
                "round": index,
                "order": order,
                "started_at": "2026-09-23T10:15:00.000Z",
                "warmup": False,
                "duration_s": 0.01,
            })
            entry["sample_extra"].append(None)
    if failed_arms is not None:
        entry["failed_arms"] = list(failed_arms)
    if status == "ok":
        finalize(entry, 0.95)
    return entry


def make_doc(
    entries: Sequence[BenchmarkDoc],
    *,
    machine: MachineDoc | None = None,
    policy: Policy | None = None,
    invocation_id: str = "11111111-2222-3333-4444-555555555555",
    started_at: str = "2026-09-23T10:15:00Z",
    seed: int = 1234,
    arms: Sequence[str] = ("A",),
) -> ResultDoc:
    """Build a result document.

    Args:
        entries: The benchmark entries.
        machine: The machine entry.
        policy: The policy.
        invocation_id: The invocation id.
        started_at: The invocation start time.
        seed: The invocation seed.
        arms: The arms, each with the same subject.

    Returns:
        The document.
    """
    return {
        "schema": SCHEMA_ID,
        "tool": {"name": "reflex-bench", "version": "0.1.0"},
        "invocation": {
            "id": invocation_id,
            "argv": ["run", "--suite", "selftest"],
            "started_at": started_at,
            "duration_s": 42.1,
            "mode": "local",
            "kind": "local",
            "ci": None,
            "rng_seed": seed,
        },
        "subjects": {arm: make_subject().to_doc() for arm in arms},
        "machine": machine or make_machine(),
        "fixture": None,
        "policy": (policy or Policy()).to_doc(),
        "benchmarks": list(entries),
    }


def make_load_result(**changes: Any) -> LoadResult:
    """Build a healthy open-loop load result.

    Args:
        **changes: Fields to override.

    Returns:
        The result.
    """
    values: dict[str, Any] = {
        "sessions": 10,
        "mode": "open",
        "processes": 1,
        "cpus": None,
        "reflex_version": "0.9.12",
        "warmup_s": 10.0,
        "duration_s": 30.0,
        "offered_rate": 400.0,
        "achieved_send_rate": 399.8,
        "answered_rate": 399.8,
        "sent": 11994,
        "answered": 11994,
        "unanswered": 0,
        "out_of_order": 0,
        "session_errors": [],
        "response_s": {
            "p50": 0.0031,
            "p90": 0.0052,
            "p99": 0.0119,
            "p999": 0.031,
            "max": 0.044,
        },
        "service_s": {"p50": 0.003, "p99": 0.0117, "max": 0.044},
        "lag_s": {"p50": 4e-05, "p99": 0.00021, "max": 0.0009},
        "generator_cpu_fraction": 0.18,
        "prime_s": {"p50": 0.09, "max": 0.21},
        "histogram": {"of": "response_s", "lo_s": 1e-05, "hi_s": 100.0, "counts": []},
        "reply_frame": None,
    }
    return LoadResult(**{**values, **changes})
