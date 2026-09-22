"""Runs benchmark instances: hooks, warmup, run counts, timeouts and failure capture.

For each instance the order is ``setup_cache`` (once per subject and parameter
set), ``setup``, then ``prepare`` → ``sample`` → ``conclude`` per run, then
``cleanup``. ``conclude`` and ``cleanup`` always run. Every hook of an instance
runs on one worker thread (so thread-bound resources such as a sync Playwright
browser work across hooks) under a deadline; a hook that misses it ends the
instance with status ``timeout``, and the remaining teardown hooks run on a
fresh thread while the stuck one is abandoned. Any exception ends the instance
with status ``failed``; other instances still run.
"""

from __future__ import annotations

import concurrent.futures
import functools
import hashlib
import logging
import math
import queue
import random
import shutil
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from packaging.version import InvalidVersion, Version

from reflex_bench import stats
from reflex_bench.context import Context, Subject, base_env
from reflex_bench.registry import Benchmark, Instance, ParamSet, SampleResult
from reflex_bench.schema import (
    FAIL_ON,
    BenchmarkDoc,
    FailOn,
    PolicyDoc,
    SampleMetaDoc,
    SummaryDoc,
    format_name,
    sample_indices,
    timed_values,
)
from reflex_bench.store import cache_dir, slug

TRACEBACK_LINES = 50
CORRECTION = "holm"

Event = dict[str, Any]
_T = TypeVar("_T")


def utc_now(timespec: str = "milliseconds") -> str:
    """Return the current UTC time in ISO 8601 with a ``Z`` suffix.

    Args:
        timespec: The precision, as for :meth:`datetime.isoformat`.

    Returns:
        E.g. ``2026-09-23T10:15:00.123Z``.
    """
    return (
        datetime.now(timezone.utc).isoformat(timespec=timespec).replace("+00:00", "Z")
    )


def derive_seed(seed: int, *parts: str) -> int:
    """Derive an independent, reproducible seed for one stream of random numbers.

    Args:
        seed: The invocation seed.
        *parts: What the stream is for, e.g. an instance name and an arm.

    Returns:
        A 64-bit seed that does not depend on which other streams exist.
    """
    digest = hashlib.sha256(":".join((str(seed), *parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")


@dataclass(frozen=True)
class Policy:
    """Every setting that shapes the samples and the verdicts.

    Attributes:
        runs: A fixed number of timed runs; ``None`` applies the automatic rule.
        min_runs: The fewest timed runs of the automatic rule.
        max_runs: The most timed runs of the automatic rule.
        min_time_s: The measuring time the automatic rule aims for.
        warmup: Untimed runs; ``None`` uses each benchmark's own value.
        timeout_s: Seconds per prepare/sample/conclude; ``None`` uses each
            benchmark's own value.
        smoke: One run, no warmup, no statistics: only checks that benchmarks work.
        alpha: The significance level of comparisons.
        threshold_rel: The practical threshold of comparisons, as a fraction.
        confidence: The confidence level of all intervals.
        bootstrap_resamples: Bootstrap resamples for the change CI.
        fail_on: ``regression`` to exit with 2 when a comparison regresses.
        fail_on_inconclusive: Exit with 3 when a comparison is inconclusive.
    """

    runs: int | None = None
    min_runs: int = 10
    max_runs: int = 30
    min_time_s: float = 30.0
    warmup: int | None = None
    timeout_s: float | None = None
    smoke: bool = False
    alpha: float = 0.01
    threshold_rel: float = 0.03
    confidence: float = 0.95
    bootstrap_resamples: int = 10_000
    fail_on: FailOn = "never"
    fail_on_inconclusive: bool = False

    def __post_init__(self) -> None:
        """Validate the settings.

        Raises:
            ValueError: On an out-of-range setting.
        """
        problems = [
            message
            for bad, message in (
                (self.runs is not None and self.runs < 1, "runs must be >= 1"),
                (self.min_runs < 1, "min-runs must be >= 1"),
                (self.max_runs < self.min_runs, "max-runs must be >= min-runs"),
                (self.min_time_s < 0, "min-time must be >= 0"),
                (self.warmup is not None and self.warmup < 0, "warmup must be >= 0"),
                (
                    self.timeout_s is not None and self.timeout_s <= 0,
                    "timeout must be > 0",
                ),
                (not 0 < self.alpha < 1, "alpha must be between 0 and 1"),
                (self.threshold_rel < 0, "threshold must be >= 0"),
                (not 0 < self.confidence < 1, "confidence must be between 0 and 1"),
                (self.bootstrap_resamples < 1, "bootstrap resamples must be >= 1"),
                (self.fail_on not in FAIL_ON, f"fail-on must be one of {FAIL_ON}"),
            )
            if bad
        ]
        if problems:
            raise ValueError("; ".join(problems))

    def auto_runs(self, first_sample_s: float) -> int:
        """Apply hyperfine's run-count rule after the first timed sample.

        Args:
            first_sample_s: The duration of the first timed sample.

        Returns:
            ``clamp(max(min_runs, ceil(min_time / first)), min_runs, max_runs)``.
        """
        if first_sample_s <= 0:
            return self.max_runs
        wanted = max(self.min_runs, math.ceil(self.min_time_s / first_sample_s))
        return min(wanted, self.max_runs)

    def to_doc(self) -> PolicyDoc:
        """Describe the policy for the result document.

        Returns:
            The policy entry.
        """
        return {
            "runs": self.runs,
            "min_runs": self.min_runs,
            "max_runs": self.max_runs,
            "min_time_s": self.min_time_s,
            "warmup": self.warmup,
            "timeout_s": self.timeout_s,
            "smoke": self.smoke,
            "alpha": self.alpha,
            "correction": CORRECTION,
            "threshold_rel": self.threshold_rel,
            "confidence": self.confidence,
            "bootstrap_resamples": self.bootstrap_resamples,
            "fail_on": self.fail_on,
            "fail_on_inconclusive": self.fail_on_inconclusive,
        }


@dataclass(frozen=True)
class Planned:
    """A benchmark instance waiting to run.

    Attributes:
        benchmark: The benchmark definition.
        params: The parameter set.
    """

    benchmark: Benchmark
    params: ParamSet

    @property
    def name(self) -> str:
        """The instance name.

        Returns:
            ``id`` or ``id[key=value,...]``.
        """
        return format_name(self.benchmark.id, self.params.params)


def plan(
    benchmarks: Sequence[Benchmark], overrides: Mapping[str, object] | None = None
) -> list[Planned]:
    """Expand benchmarks into the instances to run.

    Args:
        benchmarks: The selected benchmarks.
        overrides: ``--param`` overrides.

    Returns:
        The instances, benchmark by benchmark, in parameter-grid order.
    """
    return [
        Planned(bench, params)
        for bench in benchmarks
        for params in bench.expand(overrides)
    ]


def unsupported_reason(bench: Benchmark, subject: Subject) -> str | None:
    """Explain why a subject is too old for a benchmark.

    Args:
        bench: The benchmark.
        subject: The reflex installation under test.

    Returns:
        The reason, or ``None`` when the benchmark supports the subject.
    """
    if bench.min_version is None:
        return None
    if subject.reflex_version is None:
        return f"requires reflex >= {bench.min_version}; reflex is not installed"
    try:
        version = Version(subject.reflex_version)
    except InvalidVersion:
        return f"requires reflex >= {bench.min_version}; cannot parse {subject.reflex_version!r}"
    if version < Version(bench.min_version):
        return f"requires reflex >= {bench.min_version} (subject has {version})"
    return None


class HookTimeoutError(Exception):
    """A hook did not return within its deadline."""

    def __init__(self, hook: str, timeout: float, stack: list[str]) -> None:
        """Describe the timeout.

        Args:
            hook: The hook name.
            timeout: The deadline in seconds.
            stack: Where the hook was stuck.
        """
        super().__init__(f"{hook}() exceeded the {timeout:g} s timeout")
        self.stack = stack


class _StuckError(Exception):
    """The worker did not finish a job in time."""


class _Worker:
    """A daemon thread that runs jobs in submission order.

    Daemon, so a thread stuck in a hung hook cannot keep the process alive.
    """

    def __init__(self, name: str) -> None:
        """Start the thread.

        Args:
            name: The thread name.
        """
        self._jobs: queue.SimpleQueue[tuple[Callable[[], Any], Future[Any]] | None] = (
            queue.SimpleQueue()
        )
        self._thread = threading.Thread(target=self._loop, name=name, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        """Run jobs until :meth:`close`."""
        while (job := self._jobs.get()) is not None:
            fn, future = job
            if not future.set_running_or_notify_cancel():
                continue
            try:
                result = fn()
            except Exception as exc:
                future.set_exception(exc)
            except BaseException as exc:
                # sys.exit() in a hook must fail the benchmark, not end the harness.
                error = RuntimeError(f"hook raised {type(exc).__name__}: {exc}")
                error.__cause__ = exc
                future.set_exception(error)
            else:
                future.set_result(result)

    def run(self, fn: Callable[[], _T], timeout: float) -> _T:
        """Run a job and wait for it.

        Args:
            fn: The job.
            timeout: Seconds to wait.

        Returns:
            The job's result.

        Raises:
            _StuckError: When the job is still running after ``timeout`` seconds.
        """
        future: Future[_T] = Future()
        self._jobs.put((fn, future))
        done, _ = concurrent.futures.wait((future,), timeout=timeout)
        if not done:
            raise _StuckError
        return future.result()

    def stack(self) -> list[str]:
        """Capture where the thread currently is.

        Returns:
            The formatted stack of the thread.
        """
        frame = sys._current_frames().get(self._thread.ident or -1)
        return traceback.format_stack(frame) if frame is not None else []

    def close(self) -> None:
        """Let the thread exit once its current job returns."""
        self._jobs.put(None)


class _Hooks:
    """Runs one instance's hooks under deadlines, replacing a stuck worker."""

    def __init__(self, name: str) -> None:
        """Start the worker.

        Args:
            name: The worker thread name.
        """
        self._name = name
        self._worker = _Worker(name)
        self.secondary: list[Exception] = []

    def call(self, hook: str, fn: Callable[[], _T], timeout: float) -> _T:
        """Run a hook on the worker thread.

        Args:
            hook: The hook name, for messages.
            fn: The hook.
            timeout: Seconds allowed.

        Returns:
            The hook's result.

        Raises:
            HookTimeoutError: When the hook misses its deadline. Later hooks run on a
                fresh thread.
        """
        try:
            return self._worker.run(fn, timeout)
        except _StuckError:
            stack = self._worker.stack()
            self._worker.close()
            self._worker = _Worker(self._name)
            raise HookTimeoutError(hook, timeout, stack) from None

    def call_quietly(self, hook: str, fn: Callable[[], object], timeout: float) -> None:
        """Run a teardown hook after a failure, keeping its error as secondary.

        Args:
            hook: The hook name.
            fn: The hook.
            timeout: Seconds allowed.
        """
        try:
            self.call(hook, fn, timeout)
        except Exception as exc:
            self.secondary.append(exc)

    def close(self) -> None:
        """Stop the worker thread."""
        self._worker.close()


def _timed(fn: Callable[[], _T]) -> tuple[_T, int]:
    """Call a function and measure its wall time.

    Args:
        fn: The function.

    Returns:
        Its result and the elapsed ``perf_counter_ns`` nanoseconds.
    """
    start = time.perf_counter_ns()
    result = fn()
    return result, time.perf_counter_ns() - start


def new_entry(planned: Planned) -> BenchmarkDoc:
    """Create the result entry of an instance, before any sample.

    Args:
        planned: The instance.

    Returns:
        An ``ok`` entry with every declared metric and no samples.
    """
    bench = planned.benchmark
    entry: BenchmarkDoc = {
        "id": bench.id,
        "params": dict(planned.params.params),
        "kind": bench.kind,
        "version": bench.version,
        "status": "ok",
        "error": None,
        "traceback_tail": None,
        "dims": {},
        "metrics": {
            name: {
                "unit": metric.unit,
                "direction": metric.direction,
                "assume": metric.assume,
                "samples": {},
                "summary": {},
                "comparison": None,
                "warnings": [],
            }
            for name, metric in bench.metrics.items()
        },
        "sample_meta": [],
        "sample_extra": [],
    }
    if planned.params.hidden:
        entry["hidden_params"] = dict(planned.params.hidden)
    return entry


def _record_sample(
    entry: BenchmarkDoc, result: SampleResult, meta: SampleMetaDoc
) -> None:
    """Append one sample to an entry.

    Args:
        entry: The benchmark entry.
        result: The normalized sample.
        meta: When and how it was taken.
    """
    for name, value in result.values.items():
        entry["metrics"][name]["samples"].setdefault(meta["arm"], []).append(value)
    entry["sample_meta"].append(meta)
    entry["sample_extra"].append(result.extra)


def _format_error(exc: BaseException) -> str:
    """Describe an exception in one line.

    Args:
        exc: The exception.

    Returns:
        ``Type: message``, or just the message for a timeout.
    """
    if isinstance(exc, HookTimeoutError):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


def _record_failure(entry: BenchmarkDoc, errors: Sequence[BaseException]) -> None:
    """Mark an entry as failed or timed out.

    Args:
        entry: The benchmark entry.
        errors: The first error and any raised by teardown hooks after it.
    """
    primary = errors[0]
    if isinstance(primary, HookTimeoutError):
        entry["status"] = "timeout"
        lines = ["hook was stuck at:\n", *primary.stack]
    else:
        entry["status"] = "failed"
        lines = traceback.format_exception(
            type(primary), primary, primary.__traceback__
        )
    tail = "".join(lines).splitlines()[-TRACEBACK_LINES:]
    tail.extend(f"also: {_format_error(exc)}" for exc in errors[1:])
    entry["error"] = _format_error(primary)
    entry["traceback_tail"] = "\n".join(tail)


def _outlier_warning(
    entry: BenchmarkDoc, arm: str, values: Sequence[float], summary: SummaryDoc
) -> str | None:
    """Describe severe outliers; they are kept in the data.

    Args:
        entry: The benchmark entry.
        arm: The arm.
        values: The arm's timed samples of one metric.
        summary: Their summary.

    Returns:
        E.g. ``1 severe outlier (sample 7: +31 %). Kept.``, or ``None``.
    """
    if not summary["outliers"]["severe"]:
        return None
    stored = sample_indices(entry, arm)
    median = summary["median"]
    described = [
        f"{stored[i]}: {100 * (values[i] / median - 1):+.0f} %"
        if median
        else str(stored[i])
        for i in stats.tukey_outliers(values).severe
    ]
    count = len(described)
    plural = "s" if count > 1 else ""
    return (
        f"{count} severe outlier{plural} (sample{plural} {', '.join(described)}). Kept."
    )


def finalize(entry: BenchmarkDoc, confidence: float) -> None:
    """Derive summaries and warnings from an entry's timed samples.

    Warmup samples are excluded. Exact metrics warn about any variance; other
    metrics get the stability and severe-outlier warnings.

    Args:
        entry: The benchmark entry, updated in place.
        confidence: The confidence level of the median CI.
    """
    arms = sorted({meta["arm"] for meta in entry["sample_meta"]})
    for name, metric in entry["metrics"].items():
        metric["summary"] = {}
        metric["warnings"] = []
        for arm in arms:
            values = timed_values(entry, name, arm)
            if not values:
                continue
            summary = stats.summarize(values, confidence)
            metric["summary"][arm] = summary
            if metric["assume"] == "exact":
                found = (
                    [
                        (
                            f"exact metric varied across {summary['n']} samples:"
                            f" {summary['min']:g} to {summary['max']:g} {metric['unit']}"
                        )
                    ]
                    if summary["min"] != summary["max"]
                    else []
                )
            else:
                found = stats.stability_warnings(values, values[0], metric["direction"])
                if outliers := _outlier_warning(entry, arm, values, summary):
                    found.append(outliers)
            prefix = f"[{arm}] " if len(arms) > 1 else ""
            metric["warnings"].extend(prefix + warning for warning in found)


class Scheduler:
    """Runs planned instances against one subject under one policy."""

    def __init__(
        self,
        subject: Subject,
        policy: Policy,
        *,
        home: Path,
        seed: int,
        keep: bool = False,
        on_event: Callable[[Event], None] | None = None,
    ) -> None:
        """Configure a run.

        Args:
            subject: The reflex installation under test.
            policy: Run counts, warmup, timeouts and statistics settings.
            home: The bench home, for ``setup_cache`` directories.
            seed: The invocation seed; each instance derives its own RNG from it.
            keep: Keep each instance's work directory instead of removing it.
            on_event: Receives progress events (``benchmark_start``, ``sample``,
                ``benchmark_end``).
        """
        self.subject = subject
        self.policy = policy
        self.home = home
        self.seed = seed
        self.keep = keep
        self.on_event = on_event
        self.kept: list[Path] = []
        self._cache_done: set[tuple[str, str]] = set()

    def _emit(self, event: Event) -> None:
        """Send a progress event to the listener, if any.

        Args:
            event: The event.
        """
        if self.on_event is not None:
            self.on_event(event)

    def run(self, planned: Sequence[Planned]) -> list[BenchmarkDoc]:
        """Run instances one after the other.

        Args:
            planned: The instances.

        Returns:
            One result entry per instance, whatever its status.
        """
        return [
            self.run_one(item, index=index, total=len(planned))
            for index, item in enumerate(planned)
        ]

    def run_one(
        self, planned: Planned, *, index: int = 0, total: int = 1, arm: str = "A"
    ) -> BenchmarkDoc:
        """Run one instance.

        Args:
            planned: The instance.
            index: Its position in the run, for progress events.
            total: The number of instances in the run.
            arm: The arm being measured.

        Returns:
            The result entry.
        """
        name = planned.name
        entry = new_entry(planned)
        self._emit({
            "event": "benchmark_start",
            "id": name,
            "index": index,
            "total": total,
        })
        started = time.perf_counter()
        reason = unsupported_reason(planned.benchmark, self.subject)
        if reason is not None:
            entry["status"] = "unsupported"
            entry["error"] = reason
        else:
            self._execute(planned, entry, arm)
            if entry["status"] == "ok" and not self.policy.smoke:
                finalize(entry, self.policy.confidence)
        self._emit({
            "event": "benchmark_end",
            "id": name,
            "index": index,
            "total": total,
            "status": entry["status"],
            "error": entry["error"],
            "n": sum(not meta["warmup"] for meta in entry["sample_meta"]),
            "elapsed_s": round(time.perf_counter() - started, 6),
        })
        return entry

    def _context(self, planned: Planned, arm: str) -> Context:
        """Create the context of an instance.

        Args:
            planned: The instance.
            arm: The arm being measured.

        Returns:
            A context with a fresh work directory, the persistent cache directory of
            the subject and benchmark (shared by its parameter sets) and a seeded RNG.
        """
        cache = cache_dir(self.home, self.subject.spec, planned.benchmark.id)
        cache.mkdir(parents=True, exist_ok=True)
        return Context(
            subject=self.subject,
            params=planned.params.merged,
            workdir=Path(
                tempfile.mkdtemp(prefix=f"reflex-bench-{slug(planned.name)}-")
            ),
            cache_dir=cache,
            env=base_env(),
            rng=random.Random(derive_seed(self.seed, planned.name, arm)),
            log=logging.getLogger(f"reflex_bench.{planned.benchmark.id}"),
            arm=arm,
        )

    def _execute(self, planned: Planned, entry: BenchmarkDoc, arm: str) -> None:
        """Run an instance's hooks and record its samples or its failure.

        Args:
            planned: The instance.
            entry: Its result entry, updated in place.
            arm: The arm being measured.
        """
        bench = planned.benchmark
        hooks = _Hooks(f"reflex-bench {planned.name}")
        errors: list[BaseException] = []
        ctx: Context | None = None
        instance: Instance | None = None
        try:
            ctx = self._context(planned, arm)
            instance = Instance(bench, planned.params, ctx)
            cache_key = (self.subject.spec, planned.name)
            if cache_key not in self._cache_done:
                hooks.call("setup_cache", instance.setup_cache, bench.setup_timeout)
                self._cache_done.add(cache_key)
            hooks.call("setup", instance.setup, bench.setup_timeout)
            self._sample(instance, hooks, entry, arm)
        except Exception as exc:
            errors.append(exc)
        finally:
            if instance is not None:
                if errors:
                    hooks.call_quietly("cleanup", instance.cleanup, bench.setup_timeout)
                else:
                    try:
                        hooks.call("cleanup", instance.cleanup, bench.setup_timeout)
                    except Exception as exc:
                        errors.append(exc)
            hooks.close()
            if ctx is not None and self.keep:
                self.kept.append(ctx.workdir)
            elif ctx is not None:
                shutil.rmtree(ctx.workdir, ignore_errors=True)
        errors.extend(hooks.secondary)
        if errors:
            _record_failure(entry, errors)

    def _sample(
        self, instance: Instance, hooks: _Hooks, entry: BenchmarkDoc, arm: str
    ) -> None:
        """Take warmup and timed samples until the run count is reached.

        Args:
            instance: The bound benchmark.
            hooks: The hook runner.
            entry: The result entry, updated in place.
            arm: The arm being measured.
        """
        bench = instance.benchmark
        policy = self.policy
        timeout = policy.timeout_s or bench.timeout
        if policy.smoke:
            warmup, target = 0, 1
        else:
            warmup = bench.warmup if policy.warmup is None else policy.warmup
            target = policy.runs or (1 if bench.exact else None)
        timed = 0
        index = 0
        while target is None or timed < target:
            is_warmup = index < warmup
            try:
                hooks.call("prepare", instance.prepare, timeout)
                started_at = utc_now()
                raw, elapsed_ns = hooks.call(
                    "sample", functools.partial(_timed, instance.sample), timeout
                )
            except BaseException:
                hooks.call_quietly("conclude", instance.conclude, timeout)
                raise
            hooks.call("conclude", instance.conclude, timeout)
            duration = elapsed_ns / 1e9
            result = bench.normalize(raw, duration)
            _record_sample(
                entry,
                result,
                {
                    "arm": arm,
                    "round": 0,
                    "order": 0,
                    "started_at": started_at,
                    "warmup": is_warmup,
                    "duration_s": duration,
                },
            )
            if not is_warmup:
                timed += 1
                if target is None:
                    target = policy.auto_runs(duration)
            self._emit({
                "event": "sample",
                "id": instance.name,
                "index": index,
                "warmup": is_warmup,
                "timed": timed,
                "target": target,
                "duration_s": duration,
                "values": dict(result.values),
            })
            index += 1
