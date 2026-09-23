"""Runs benchmark instances: hooks, warmup, run counts, timeouts and failure capture.

For each instance the order is ``setup_cache`` (once per subject and parameter
set), ``setup``, then ``prepare`` → ``sample`` → ``conclude`` per run, then
``cleanup``. ``conclude`` and ``cleanup`` always run. Every hook of an instance
runs on one worker thread (so thread-bound resources such as a sync Playwright
browser work across hooks) under a deadline; a hook that misses it ends the
instance with status ``timeout``, and the remaining teardown hooks run on a
fresh thread while the stuck one is abandoned. An interrupt (Ctrl-C) during a
hook also moves the teardown hooks to a fresh thread. An abandoned hook gets
:data:`ABANDON_GRACE_S` after teardown to return; if it does not, the work
directory is kept and the benchmark's remaining parameter sets are skipped. Any
exception ends the instance with status ``failed``; other instances still run.

:meth:`Scheduler.open` holds an instance open so a caller can take samples one
at a time, e.g. interleaving two arms.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
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
from collections.abc import Callable, Iterator, Mapping, Sequence
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
ABANDON_GRACE_S = 5.0
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
        """Check the settings that depend on each other.

        Single settings are range-checked where they are parsed (the CLI options).

        Raises:
            ValueError: When ``max_runs`` is below ``min_runs``.
        """
        if self.max_runs < self.min_runs:
            msg = "max-runs must be >= min-runs"
            raise ValueError(msg)

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

    def join(self, timeout: float) -> bool:
        """Wait for the thread to exit after :meth:`close`.

        Args:
            timeout: Seconds to wait.

        Returns:
            Whether the thread is still running.
        """
        self._thread.join(timeout)
        return self._thread.is_alive()


class _Hooks:
    """Runs one instance's hooks under deadlines, replacing a stuck worker."""

    def __init__(self, name: str) -> None:
        """Start the worker.

        Args:
            name: The worker thread name.
        """
        self._name = name
        self._worker = _Worker(name)
        self._abandoned: list[tuple[str, _Worker]] = []
        self.secondary: list[Exception] = []

    def _abandon(self, hook: str) -> None:
        """Leave the worker to its running hook and continue on a fresh thread.

        Args:
            hook: The running hook.
        """
        self._worker.close()
        self._abandoned.append((hook, self._worker))
        self._worker = _Worker(self._name)

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
                fresh thread, as they do after an interrupt while waiting.
        """
        try:
            return self._worker.run(fn, timeout)
        except _StuckError:
            stack = self._worker.stack()
            self._abandon(hook)
            raise HookTimeoutError(hook, timeout, stack) from None
        except BaseException as exc:
            # Hook errors arrive as Exception; anything else interrupted the wait.
            if not isinstance(exc, Exception):
                self._abandon(hook)
            raise

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

    def close(self) -> list[str]:
        """Stop the worker thread and give abandoned hooks a grace period to return.

        Returns:
            The abandoned hooks still running after :data:`ABANDON_GRACE_S`.
        """
        self._worker.close()
        deadline = time.monotonic() + ABANDON_GRACE_S
        return [
            hook
            for hook, worker in self._abandoned
            if worker.join(max(0.0, deadline - time.monotonic()))
        ]


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


def make_context(
    subject: Subject, planned: Planned, *, home: Path, seed: int, arm: str = "A"
) -> Context:
    """Create the context of a benchmark instance, as the scheduler does.

    Args:
        subject: The reflex installation under test.
        planned: The instance.
        home: The bench home, for the ``setup_cache`` directory.
        seed: The invocation seed.
        arm: The arm being measured.

    Returns:
        A context with a fresh work directory, the persistent (created) cache
        directory of the subject identity and parameter set, and an RNG seeded
        from ``seed``, the instance name and the arm.
    """
    cache = cache_dir(
        home, subject.identity, planned.benchmark.id, planned.params.params
    )
    cache.mkdir(parents=True, exist_ok=True)
    return Context(
        subject=subject,
        params=planned.params.merged,
        workdir=Path(tempfile.mkdtemp(prefix=f"reflex-bench-{slug(planned.name)}-")),
        cache_dir=cache,
        env=base_env(),
        rng=random.Random(derive_seed(seed, planned.name, arm)),
        log=logging.getLogger(f"reflex_bench.{planned.benchmark.id}"),
        arm=arm,
    )


class Session:
    """A benchmark instance held open by :meth:`Scheduler.open`.

    ``setup`` has run; each :meth:`sample_once` runs ``prepare`` → ``sample`` →
    ``conclude`` and records the sample in ``entry``. :meth:`close` runs
    ``cleanup`` and records any failure in ``entry``.

    Attributes:
        planned: The instance.
        entry: The result entry the samples and any failure go to.
        arm: The arm being measured.
        ctx: The context of the hooks; ``None`` when it could not be created.
    """

    def __init__(
        self, scheduler: Scheduler, planned: Planned, entry: BenchmarkDoc, arm: str
    ) -> None:
        """Prepare the session; :meth:`Scheduler.open` then runs the setup hooks.

        Args:
            scheduler: The scheduler that opened it.
            planned: The instance.
            entry: The result entry.
            arm: The arm being measured.
        """
        self.planned = planned
        self.entry = entry
        self.arm = arm
        self.ctx: Context | None = None
        self._scheduler = scheduler
        self._hooks = _Hooks(f"reflex-bench {planned.name}")
        self._instance: Instance | None = None
        self._errors: list[Exception] = []
        self._timeout = scheduler.policy.timeout_s or planned.benchmark.timeout
        self._closed = False

    def _setup(self) -> None:
        """Create the context and run the setup hooks.

        ``setup_cache`` runs once per cache directory, then ``setup`` runs.
        """
        bench = self.planned.benchmark
        scheduler = self._scheduler
        try:
            self.ctx = make_context(
                scheduler.subject,
                self.planned,
                home=scheduler.home,
                seed=scheduler.seed,
                arm=self.arm,
            )
            self._instance = Instance(bench, self.planned.params, self.ctx)
            if self.ctx.cache_dir not in scheduler._cache_done:
                self._hooks.call(
                    "setup_cache", self._instance.setup_cache, bench.setup_timeout
                )
                scheduler._cache_done.add(self.ctx.cache_dir)
            self._hooks.call("setup", self._instance.setup, bench.setup_timeout)
        except Exception as exc:
            self._errors.append(exc)

    def sample_once(
        self, *, round: int, order: int, warmup: bool
    ) -> tuple[SampleResult, float] | None:
        """Take one sample and record it in the entry.

        Args:
            round: The round the sample belongs to.
            order: The sample's position within its round.
            warmup: Whether the sample is excluded from statistics.

        Returns:
            The normalized sample and its duration in seconds, or ``None`` when a
            hook failed now or earlier (the failure is recorded on :meth:`close`).
        """
        instance = self._instance
        if self._errors or instance is None:
            return None
        hooks, timeout = self._hooks, self._timeout
        try:
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
            result = instance.benchmark.normalize(raw, duration)
        except Exception as exc:
            self._errors.append(exc)
            return None
        _record_sample(
            self.entry,
            result,
            {
                "arm": self.arm,
                "round": round,
                "order": order,
                "started_at": started_at,
                "warmup": warmup,
                "duration_s": duration,
            },
        )
        return result, duration

    def close(self) -> None:
        """Run ``cleanup``, remove the work directory and record any failure.

        A hook still running after teardown keeps the work directory and makes
        the scheduler skip the benchmark's remaining parameter sets.
        """
        if self._closed:
            return
        self._closed = True
        hooks, bench = self._hooks, self.planned.benchmark
        if self._instance is not None:
            if self._errors:
                hooks.call_quietly(
                    "cleanup", self._instance.cleanup, bench.setup_timeout
                )
            else:
                try:
                    hooks.call("cleanup", self._instance.cleanup, bench.setup_timeout)
                except Exception as exc:
                    self._errors.append(exc)
        stuck = hooks.close()
        errors = [*self._errors, *hooks.secondary]
        if stuck:
            reason = (
                f"{stuck[0]}() of {self.planned.name} was still running after teardown"
            )
            self._scheduler._stuck[bench.id] = reason
            errors.append(RuntimeError(f"{reason}; its work directory was kept"))
        if self.ctx is not None:
            if stuck or self._scheduler.keep:
                self._scheduler.kept.append(self.ctx.workdir)
            else:
                shutil.rmtree(self.ctx.workdir, ignore_errors=True)
        if errors:
            _record_failure(self.entry, errors)


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
        self._cache_done: set[Path] = set()
        self._stuck: dict[str, str] = {}

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

    @contextlib.contextmanager
    def open(
        self, planned: Planned, entry: BenchmarkDoc, *, arm: str = "A"
    ) -> Iterator[Session]:
        """Set up an instance and hold it open for :meth:`Session.sample_once`.

        Several sessions can be open at once, e.g. one per arm to interleave
        their samples into one entry. Leaving the block closes the session.

        Args:
            planned: The instance.
            entry: The result entry the samples and any failure go to.
            arm: The arm being measured.

        Yields:
            The session; after a setup failure it takes no samples.
        """
        session = Session(self, planned, entry, arm)
        try:
            session._setup()
            yield session
        finally:
            session.close()

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
        stuck = self._stuck.get(planned.benchmark.id)
        if reason is not None:
            entry["status"] = "unsupported"
            entry["error"] = reason
        elif stuck is not None:
            entry["status"] = "skipped"
            entry["error"] = stuck
        else:
            with self.open(planned, entry, arm=arm) as session:
                self._sample(session)
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

    def _sample(self, session: Session) -> None:
        """Take warmup and timed samples until the run count is reached or a hook fails.

        Args:
            session: The open instance.
        """
        bench = session.planned.benchmark
        policy = self.policy
        if policy.smoke:
            warmup, target = 0, 1
        else:
            warmup = bench.warmup if policy.warmup is None else policy.warmup
            target = policy.runs or (1 if bench.exact else None)
        timed = 0
        index = 0
        while target is None or timed < target:
            is_warmup = index < warmup
            taken = session.sample_once(round=0, order=0, warmup=is_warmup)
            if taken is None:
                return
            result, duration = taken
            if not is_warmup:
                timed += 1
                if target is None:
                    target = policy.auto_runs(duration)
            self._emit({
                "event": "sample",
                "id": session.planned.name,
                "index": index,
                "warmup": is_warmup,
                "timed": timed,
                "target": target,
                "duration_s": duration,
                "values": dict(result.values),
            })
            index += 1
