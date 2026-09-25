r"""Measure what the engine costs, against a real Postgres and real worker processes.

Run the whole set, or one scenario at a time:

    REFLEX_TEST_POSTGRES=postgresql://postgres@127.0.0.1:5432/bench \\
        uv run python packages/reflex-workflow/benchmarks/bench.py all --repeat 3

Every number here is one machine's; see README.md for what that does and does not
tell you. The workers are separate processes, so the figures include the
connection pooling and the claim contention a deployment would have, but not the
network between an application and its database.

Nothing is reported that the rows themselves contradict: every run records which
worker ran it and when, and a scenario in which any worker ran more at once than
its cap, or any customer more than its limit, fails instead of printing.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import contextlib
import datetime
import json
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Iterable
from typing import Any

from reflex_workflow import AttemptLog, Limit, Workflow, model, run_workflows, step
from sqlalchemy import DateTime, String, func, insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

URL = os.environ["REFLEX_TEST_POSTGRES"]
ASYNC_URL = URL.replace("postgresql://", "postgresql+psycopg://", 1)

# What each worker process may run at once.
MAX_CONCURRENCY = 8

# How often an idle worker looks for due rows.
POLL = datetime.timedelta(milliseconds=50)

# How many groups the limited scenario spreads its work over, and how much of one
# group may run at once. The cap is high enough not to bind, so what is measured
# is the cost of claiming a group at a time rather than the wait it imposes.
GROUPS = 200
AT_ONCE = 50

# How long a step pretends to work, set from the command line in every process
# that runs one. Zero measures the engine alone, which is the worst case for
# claim contention; real work waits on something.
STEP_MS = 0.0

# How long the workers are given to start and settle before anything is seeded.
WARMUP = 3.0


class Base(DeclarativeBase):
    """Declarative base for the benchmark tables."""


class Measured(Workflow):
    """The columns and the one step both benchmark tables share.

    Unmapped, so each table below gets its own copy.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    due_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    worker: Mapped[int | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Do the step's work, recording who did it and when."""
        self.worker = os.getpid()
        self.started_at = datetime.datetime.now(datetime.timezone.utc)
        if STEP_MS:
            await asyncio.sleep(STEP_MS / 1000)
        self.finished_at = datetime.datetime.now(datetime.timezone.utc)
        self.status = "done"


class Plain(Base, Measured):
    """A run of one step, to measure what the engine itself costs."""

    __tablename__ = "bench_plain"


class Grouped(Base, Measured):
    """The same run, but claimed a group at a time because it declares a limit."""

    __tablename__ = "bench_grouped"
    __workflow_limit__ = Limit(by="customer", at_most=AT_ONCE)

    customer: Mapped[str] = mapped_column(String, index=True)


class Attempt(Base, AttemptLog):
    """Where the history scenario's attempts are recorded.

    Always declared, so the driver creates the table whichever scenario is
    running; a worker that was not asked to record history unmaps it, which is
    what an application that never declares one has.
    """

    __tablename__ = "bench_attempt"


# The driver sets this for the worker processes of the history scenario; named
# once, since a typo in either place would quietly measure the wrong thing.
HISTORY_ENV = "BENCH_HISTORY"

if not os.environ.get(HISTORY_ENV):
    model.ATTEMPTS = None


KINDS: dict[str, type[Plain | Grouped]] = {"plain": Plain, "grouped": Grouped}


def engine():
    """Build an engine for this process.

    Returns:
        A new async engine.
    """
    return create_async_engine(ASYNC_URL, pool_size=10, max_overflow=0)


async def reset(dormant: int) -> None:
    """Drop and rebuild the benchmark tables, optionally leaving dormant runs behind.

    Args:
        dormant: How many runs to leave asleep, as a population the claim query
            has to look past.
    """
    db = engine()
    async with db.begin() as conn:
        # CASCADE, because a table someone copied with LIKE while poking at plans
        # holds a dependency on the sequence and would otherwise block the drop.
        await conn.exec_driver_sql(
            "DROP TABLE IF EXISTS "
            + ", ".join(table.name for table in reversed(Base.metadata.sorted_tables))
            + " CASCADE"
        )
        await conn.run_sync(Base.metadata.create_all)
    if dormant:
        far = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        await insert_runs(db, Plain, dormant, far, batch=5000)
    await db.dispose()


async def insert_runs(
    db: Any,
    cls: type[Plain | Grouped],
    count: int,
    due: datetime.datetime,
    batch: int = 2000,
    spread: float = 0,
) -> None:
    """Insert runs directly, as an application's own writes would.

    Args:
        db: The engine to write with.
        cls: The workflow class.
        count: How many runs to insert.
        due: When they become due.
        batch: How many rows per statement.
        spread: Seconds to spread the due times over; zero makes them all due at
            once, which measures draining a backlog rather than dispatch.
    """
    factory = async_sessionmaker(db, expire_on_commit=False)
    for start in range(0, count, batch):
        rows = []
        for index in range(start, min(start + batch, count)):
            at = due + datetime.timedelta(seconds=spread * index / max(1, count))
            row: dict[str, Any] = {
                "due_at": at,
                "status": "new",
                "next_step": "work",
                "wake_at": at,
                "attempts": 0,
                "wf_version": 0,
            }
            if cls is Grouped:
                row["customer"] = f"customer-{index % GROUPS}"
            rows.append(row)
        async with factory() as session, session.begin():
            await session.execute(insert(cls), rows)


async def worker(kind: str, seconds: float) -> None:
    """Run one worker process until the driver's deadline passes.

    Args:
        kind: Which workflow table to run.
        seconds: How long to stay up.
    """
    db = engine()
    async with run_workflows(
        async_sessionmaker(db, expire_on_commit=False),
        workflows=[KINDS[kind]],
        max_concurrency=MAX_CONCURRENCY,
        poll_interval=POLL,
        lease=datetime.timedelta(seconds=30),
    ):
        await asyncio.sleep(seconds)
    await db.dispose()


def spawn(
    kind: str, count: int, seconds: float, history: bool, cpus: list[int]
) -> list[subprocess.Popen[bytes]]:
    """Start worker processes, each on its own CPU when there are enough of them.

    Args:
        kind: Which workflow table they run.
        count: How many processes.
        seconds: How long each stays up.
        history: Whether they record attempt history.
        cpus: The CPUs to pin workers to, in turn; empty leaves them unpinned.

    Returns:
        The processes.
    """
    env = {**os.environ, **({HISTORY_ENV: "1"} if history else {})}
    processes = []
    for index in range(count):
        process = subprocess.Popen(
            [
                sys.executable,
                str(pathlib.Path(__file__).resolve()),
                "worker",
                kind,
                "--seconds",
                str(seconds),
                "--step-ms",
                str(STEP_MS),
            ],
            env=env,
        )
        if cpus:
            os.sched_setaffinity(process.pid, {cpus[index % len(cpus)]})
        processes.append(process)
    return processes


async def wait_for_done(
    cls: type[Plain | Grouped], count: int, timeout: float
) -> float:
    """Wait until every run has finished.

    Args:
        cls: The workflow class.
        count: How many runs to expect.
        timeout: Seconds before giving up.

    Returns:
        How long it took.

    Raises:
        TimeoutError: If the runs do not finish in time.
    """
    db = engine()
    factory = async_sessionmaker(db, expire_on_commit=False)
    started = time.monotonic()
    done = 0
    try:
        while time.monotonic() - started < timeout:
            async with factory() as session:
                done = await session.scalar(
                    select(func.count()).select_from(cls).where(cls.status == "done")
                )
            if done and done >= count:
                return time.monotonic() - started
            await asyncio.sleep(0.02)
        msg = f"only {done} of {count} finished in {timeout}s"
        raise TimeoutError(msg)
    finally:
        await db.dispose()


def peak_overlap(
    spans: Iterable[tuple[datetime.datetime, datetime.datetime]],
) -> int:
    """Return the most spans that were open at the same moment.

    Args:
        spans: (start, end) of each span.

    Returns:
        The peak count.
    """
    # Ends sort before starts at the same instant, so back-to-back spans do not
    # count as overlapping.
    edges = sorted(
        (moment, delta)
        for start, end in spans
        for moment, delta in ((start, 1), (end, -1))
    )
    peak = live = 0
    for _, delta in edges:
        live += delta
        peak = max(peak, live)
    return peak


async def verify(cls: type[Plain | Grouped], workers: set[int]) -> dict[str, Any]:
    """Check the finished rows against what the engine promises, and time them.

    Args:
        cls: The workflow class.
        workers: The process ids of the workers this trial started.

    Returns:
        The peak concurrency seen per worker and per group, and the lateness of
        each run past its due time, in milliseconds, sorted.

    Raises:
        AssertionError: If a worker ran more at once than its cap, or a group more
            than its limit, or a process this trial did not start ran anything.
    """
    db = engine()
    columns = [cls.worker, cls.started_at, cls.finished_at, cls.due_at]
    if cls is Grouped:
        columns.append(Grouped.customer)
    async with async_sessionmaker(db)() as session:
        rows = (
            await session.execute(select(*columns).where(cls.status == "done"))
        ).all()
    await db.dispose()

    by_worker: dict[int, list[Any]] = collections.defaultdict(list)
    by_group: dict[str, list[Any]] = collections.defaultdict(list)
    for row in rows:
        by_worker[row[0]].append((row[1], row[2]))
        if cls is Grouped:
            by_group[row[4]].append((row[1], row[2]))
    worker_peak = max(peak_overlap(spans) for spans in by_worker.values())
    group_peak = max((peak_overlap(spans) for spans in by_group.values()), default=0)

    if strangers := set(by_worker) - workers:
        msg = f"processes {sorted(strangers)} ran steps; this trial did not start them"
        raise AssertionError(msg)
    if worker_peak > MAX_CONCURRENCY:
        msg = f"a worker ran {worker_peak} at once; its cap is {MAX_CONCURRENCY}"
        raise AssertionError(msg)
    if group_peak > AT_ONCE:
        msg = f"a customer ran {group_peak} at once; its limit is {AT_ONCE}"
        raise AssertionError(msg)
    return {
        "worker_peak": worker_peak,
        "group_peak": group_peak if cls is Grouped else None,
        "late_ms": sorted(
            (started - due).total_seconds() * 1000 for _, started, _, due, *_ in rows
        ),
    }


def cpu_ticks() -> dict[int, tuple[int, int]]:
    """Read how long each CPU has been busy and in total, from /proc/stat.

    Returns:
        (busy, total) jiffies per CPU.
    """
    ticks = {}
    for line in pathlib.Path("/proc/stat").read_text().splitlines():
        name, *fields = line.split()
        if name.startswith("cpu") and name != "cpu":
            values = [int(field) for field in fields]
            idle = values[3] + values[4]
            ticks[int(name[3:])] = (sum(values) - idle, sum(values))
    return ticks


def busy_share(
    before: dict[int, tuple[int, int]],
    after: dict[int, tuple[int, int]],
    cpus: list[int],
) -> float | None:
    """Return how busy a set of CPUs was between two readings, by anyone.

    Args:
        before: The earlier reading.
        after: The later reading.
        cpus: Which CPUs.

    Returns:
        The busy share, 0 to 100, or None for no CPUs.
    """
    if not cpus:
        return None
    busy = sum(after[cpu][0] - before[cpu][0] for cpu in cpus)
    total = sum(after[cpu][1] - before[cpu][1] for cpu in cpus)
    return round(100 * busy / max(1, total))


def percentile(values: list[float], share: float) -> float:
    """Return a percentile of a sorted list.

    Args:
        values: The sorted values.
        share: Which percentile, from 0 to 1.

    Returns:
        The value at that percentile.
    """
    if not values:
        return float("nan")
    return values[min(len(values) - 1, int(len(values) * share))]


async def measure(
    layout: dict[str, list[int]],
    kind: str,
    runs: int,
    workers: int,
    dormant: int = 0,
    history: bool = False,
    spread: float = 0,
) -> dict[str, Any]:
    """Run one scenario end to end, once.

    Args:
        layout: Which CPUs the workers are pinned to, and which to report on.
        kind: Which workflow table to use.
        runs: How many runs to put through it.
        workers: How many worker processes.
        dormant: How many sleeping runs to leave in the table first.
        history: Whether the workers record attempt history.
        spread: Seconds to spread the due times over; zero is a burst.

    Returns:
        What it cost.
    """
    cls = KINDS[kind]
    await reset(dormant)

    # The workers go up first and are given a moment to settle. Seeding before
    # they are polling lets them work through the backlog while the clock is
    # still being started, which reads as throughput nobody achieved.
    processes = spawn(
        kind, workers, seconds=180 + spread, history=history, cpus=layout["workers"]
    )
    # Everything after the spawn is inside the try, so a setup that fails still
    # stops the workers rather than leaving them to run into the next trial.
    try:
        await asyncio.sleep(WARMUP)

        db = engine()
        due = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=1
        )
        await insert_runs(db, cls, runs, due, spread=spread)
        # Bulk inserts leave the planner with no statistics, and without them the
        # claim falls back to a sequential scan: 6.5ms against 0.3ms on 100k rows.
        # Autovacuum does this in a running system; a benchmark has to ask.
        async with db.begin() as conn:
            await conn.exec_driver_sql(f"ANALYZE {cls.__tablename__}")
        await db.dispose()

        await asyncio.sleep(
            max(
                0.0,
                (due - datetime.datetime.now(datetime.timezone.utc)).total_seconds(),
            )
        )
        before = cpu_ticks()
        took = await wait_for_done(cls, runs, timeout=180 + spread)
        after = cpu_ticks()
        checked = await verify(cls, {process.pid for process in processes})
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=10)
    late = checked["late_ms"]
    return {
        "seconds": took,
        "steps_per_second": runs / took if not spread else None,
        "late_p50_ms": percentile(late, 0.5),
        "late_p95_ms": percentile(late, 0.95),
        "late_p99_ms": percentile(late, 0.99),
        "worker_peak": checked["worker_peak"],
        "group_peak": checked["group_peak"],
        **{
            f"busy_{name}_pct": busy_share(before, after, cpus)
            for name, cpus in layout.items()
        },
    }


def summarize(name: str, trials: list[dict[str, Any]], **shape: Any) -> dict[str, Any]:
    """Collapse repeated trials of a scenario into medians and ranges.

    Args:
        name: What the scenario is called.
        trials: Each trial's result.
        **shape: What the scenario was: runs, workers.

    Returns:
        The median of every figure, with the range of the headline ones.
    """
    summary: dict[str, Any] = {"scenario": name, **shape, "trials": len(trials)}
    for key in trials[0]:
        values = [trial[key] for trial in trials if trial[key] is not None]
        if not values:
            summary[key] = None
            continue
        summary[key] = statistics.median(values)
        if key in ("steps_per_second", "late_p95_ms"):
            summary[f"{key}_range"] = [min(values), max(values)]
    return summary


def environment(layout: dict[str, list[int]], postgres: str) -> dict[str, Any]:
    """Describe the machine and configuration the numbers came from.

    Args:
        layout: Which CPUs each part was pinned to.
        postgres: The server's version string.

    Returns:
        What to record next to the results.
    """
    cpuinfo = pathlib.Path("/proc/cpuinfo").read_text()
    model_name = next(
        (
            line.split(":", 1)[1].strip()
            for line in cpuinfo.splitlines()
            if line.startswith("model name")
        ),
        platform.processor(),
    )
    return {
        "cpu": model_name,
        "cpus": os.cpu_count(),
        "postgres": postgres,
        "python": platform.python_version(),
        "step_ms": STEP_MS,
        "max_concurrency": MAX_CONCURRENCY,
        "poll_ms": POLL.total_seconds() * 1000,
        "pinned": layout,
    }


def show(results: list[dict[str, Any]]) -> None:
    """Print the results as a table.

    Args:
        results: What each scenario cost.
    """
    columns = [
        ("scenario", 30, "{}"),
        ("workers", 7, "{}"),
        ("steps_per_second", 10, "{:.0f}"),
        ("steps_per_second_range", 12, "{}"),
        ("late_p50_ms", 8, "{:.0f}"),
        ("late_p95_ms", 8, "{:.0f}"),
        ("late_p99_ms", 8, "{:.0f}"),
        ("worker_peak", 6, "{}"),
        ("busy_workers_pct", 6, "{}"),
        ("busy_postgres_pct", 6, "{}"),
    ]
    heads = ["scenario", "workers", "steps/s", "range", "p50 ms", "p95 ms"]
    heads += ["p99 ms", "peak", "wrk %", "pg %"]
    print(
        "  ".join(
            head.ljust(width)
            for head, (_, width, _) in zip(heads, columns, strict=True)
        )
    )
    for result in results:
        cells = []
        for name, width, spec in columns:
            value = result.get(name)
            if value is None:
                cell = "-"
            elif name.endswith("_range"):
                cell = "{:.0f}-{:.0f}".format(*value)
            else:
                cell = spec.format(value)
            cells.append(cell.ljust(width))
        print("  ".join(cells))


def cpu_list(value: str) -> list[int]:
    """Parse a comma-separated CPU list.

    Args:
        value: e.g. ``4,6,8,10``.

    Returns:
        The CPUs.
    """
    return [int(cpu) for cpu in value.split(",") if cpu]


async def main() -> None:
    """Run whichever scenarios were asked for."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "what",
        choices=["all", "worker", "scaling", "limits", "population", "latency"],
    )
    parser.add_argument("kind", nargs="?", default="plain", choices=list(KINDS))
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--step-ms", type=float, default=0)
    parser.add_argument("--driver-cpu", type=int, default=None)
    parser.add_argument("--worker-cpus", type=cpu_list, default=[])
    parser.add_argument(
        "--postgres-cpus",
        type=cpu_list,
        default=[],
        help="Only reported on; pin the server yourself, e.g. with taskset.",
    )
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    global STEP_MS
    STEP_MS = args.step_ms

    if args.what == "worker":
        await worker(args.kind, args.seconds)
        return

    if args.driver_cpu is not None:
        os.sched_setaffinity(0, {args.driver_cpu})
    layout = {
        "driver": [] if args.driver_cpu is None else [args.driver_cpu],
        "workers": args.worker_cpus,
        "postgres": args.postgres_cpus,
    }
    db = engine()
    async with db.connect() as conn:
        version = (await conn.execute(text("SHOW server_version"))).scalar_one()
    await db.dispose()
    env = environment(layout, version)
    print(json.dumps(env))

    groups = {
        "scaling": [
            (f"plain x{workers}", {"kind": "plain", "workers": workers})
            for workers in (1, 2, 4)
        ],
        "limits": [
            ("grouped", {"kind": "grouped", "workers": 4}),
            ("plain+history", {"kind": "plain", "workers": 4, "history": True}),
        ],
        "population": [
            ("plain+100k dormant", {"kind": "plain", "workers": 4, "dormant": 100_000})
        ],
        # Spread out, so what is measured is how long a run waits past its time
        # rather than how long a queue takes to drain.
        "latency": [
            (
                "plain trickle",
                {"kind": "plain", "workers": 2, "runs": 300, "spread": 15},
            ),
            (
                "grouped trickle",
                {"kind": "grouped", "workers": 2, "runs": 300, "spread": 15},
            ),
        ],
    }
    scenarios = [
        (name, {"runs": args.runs, **shape})
        for group, members in groups.items()
        if args.what in ("all", group)
        for name, shape in members
    ]
    # Interleaved rather than one scenario's trials back to back, so whatever else
    # the machine is doing lands on every scenario alike instead of on one.
    trials: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for trial in range(args.repeat):
        for name, scenario in scenarios:
            trials[name].append(await measure(layout, **scenario))
            print(f"trial {trial + 1}: {name}: {json.dumps(trials[name][-1])}")
    results = [
        summarize(
            name, trials[name], runs=scenario["runs"], workers=scenario["workers"]
        )
        for name, scenario in scenarios
    ]
    show(results)
    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps({"environment": env, "results": results}, indent=2)
        )


if __name__ == "__main__":
    asyncio.run(main())
