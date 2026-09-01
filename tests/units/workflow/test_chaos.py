"""The chaos soak: random worker kills under a mixed load, then the invariants.

The boundary tests kill one worker at one named point. This kills workers at
random while they hold claims, over many runs mixing guarded effects, timers,
retries, correlated signals, and fan-out joins, then holds the contract to
its word: every run completes, every guarded effect happened exactly once,
every signal was handled exactly once, no claim is left behind.

Small by default so it runs on every push; ``REFLEX_CHAOS_SECONDS``,
``REFLEX_CHAOS_RUNS``, and ``REFLEX_CHAOS_WORKERS`` scale it into a real soak.
SQLite runs with one worker killed and restarted; Postgres runs several
workers so kills land while peers are mid-claim.
"""

import asyncio
import os
import random
import subprocess
import sys
import time
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

import pytest
from reflex_base.workflow import ChannelDelivery

from reflex.workflow.records import (
    TERMINAL_RUN_STATUSES,
    HistoryEventType,
    RunQuery,
    RunStatus,
    StepStatus,
)
from reflex.workflow.runtime import WorkflowRuntime, _close_store
from tests.units.workflow.chaos_flows import (
    LEDGER_ENV,
    WORKFLOWS,
    Payment,
    Rollout,
    Shipment,
    effects,
    open_store,
)

WORKER = Path(__file__).with_name("chaos_worker.py")
POSTGRES_URL_VAR = "REFLEX_TEST_POSTGRES"
T = TypeVar("T")

SECONDS = float(os.environ.get("REFLEX_CHAOS_SECONDS", "6"))
RUNS = int(os.environ.get("REFLEX_CHAOS_RUNS", "30"))
WORKERS = int(os.environ.get("REFLEX_CHAOS_WORKERS", "3"))
DRAIN_SECONDS = 120.0


async def sever_connections(url: str, schema: str) -> int:
    """Kill every connection to the soak's schema from the server side.

    The processes survive; their transactions do not. This is "the store
    became unreachable at commit" made real without stopping Postgres: a
    worker mid-commit sees its connection drop and must abandon the attempt,
    and every pool -- the workers' and the driver's -- must recover for the
    next call. The store names its connections after their schema, which is
    what makes them addressable here.

    Args:
        url: The database.
        schema: The soak's schema.

    Returns:
        How many backends were terminated.
    """
    import psycopg

    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
        rows = await (
            await conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE application_name = %s AND pid <> pg_backend_pid()",
                (schema,),
            )
        ).fetchall()
    return len(rows)


async def retrying(
    action: Callable[[], Awaitable[T]], *, attempts: int = 8, pause: float = 0.25
) -> T:
    """Call a store operation the way a client with an idempotency key does.

    A severed connection surfaces as an error on the driver's next call; the
    right response is the one the contract prescribes for callers -- repeat
    the same idempotent request -- not a failed test.

    Args:
        action: The coroutine factory to call.
        attempts: How many times to try.
        pause: Seconds between tries.

    Returns:
        The action's result.
    """
    attempt = 0
    while True:
        try:
            return await action()
        except Exception:
            attempt += 1
            if attempt >= attempts:
                raise
            await asyncio.sleep(pause)


@pytest.fixture(autouse=True)
def harness_store():
    """Opt out of the shared harness store parameter.

    Returns:
        The store kind this module nominally uses.
    """
    return "sqlite"


@pytest.fixture(params=["sqlite", "postgres"])
def target(request, tmp_path):
    """The store the soak runs on, and how many workers serve it.

    Args:
        request: The fixture request carrying the store kind.
        tmp_path: Temporary directory for the SQLite file.

    Yields:
        ``(target, schema, worker_count)``.
    """
    if request.param == "postgres":
        url = os.environ.get(POSTGRES_URL_VAR)
        if not url:
            pytest.skip(f"set {POSTGRES_URL_VAR} to soak against Postgres")
        schema = f"wf_chaos_{uuid.uuid4().hex}"
        yield url, schema, WORKERS
        from reflex.workflow.postgres import PostgresRunStore

        PostgresRunStore(url, schema=schema, min_size=0, max_size=1).drop_schema()
    else:
        yield str(tmp_path / "chaos.db"), "-", 1


async def test_the_engine_holds_under_random_worker_kills(
    target, tmp_path, monkeypatch
):
    """Kill workers at random under load; the documented outcomes must all hold.

    Args:
        target: The store target, schema, and worker count.
        tmp_path: Temporary directory for the ledger and worker logs.
        monkeypatch: Environment control for the ledger path.
    """
    store_target, schema, worker_count = target
    severable = store_target.startswith("postgres")
    ledger = tmp_path / "ledger.db"
    monkeypatch.setenv(LEDGER_ENV, str(ledger))
    env = {**os.environ, LEDGER_ENV: str(ledger)}
    logs: list[Path] = []

    def spawn() -> subprocess.Popen:
        """Start one worker with its own log.

        Returns:
            The worker process.
        """
        log = tmp_path / f"worker{len(logs)}.log"
        logs.append(log)
        return subprocess.Popen(
            [sys.executable, str(WORKER), store_target, schema],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=log.open("ab"),
        )

    workers = [spawn() for _ in range(worker_count)]
    store = open_store(store_target, schema)
    driver = WorkflowRuntime(store, alerts=None)
    for workflow_cls in WORKFLOWS:
        driver.register(workflow_cls)
    await driver.startup(start_worker=False)
    kernel = driver.kernel

    orders = [f"o{index}" for index in range(RUNS)]
    payments = orders[0::3]
    shipments = orders[1::3]
    rollouts = orders[2::3]
    for order in payments:
        await kernel.start(Payment.pay(order), request_key=f"pay:{order}")
    for order in shipments:
        await kernel.start(Shipment.ship(order), request_key=f"ship:{order}")
    for order in rollouts:
        await kernel.start(Rollout.begin(order), request_key=f"roll:{order}")
    expected_runs = len(orders) + 2 * len(rollouts)

    async def deliver(order: str) -> None:
        """Signal one shipment, idempotently.

        Args:
            order: The order to ship.
        """
        await retrying(
            lambda: kernel.signal_by_key(
                Shipment,
                f"ship:{order}",
                ChannelDelivery(channel="shipped", payload={"order": order}),
                key=f"evt:{order}",
            )
        )

    rng = random.Random(7)
    pending_shipments = list(shipments)
    kills = 0
    severed = 0
    died_alone: list[int] = []
    deadline = time.monotonic() + SECONDS
    try:
        while time.monotonic() < deadline:
            await asyncio.sleep(rng.uniform(0.3, 0.8))
            for index, worker in enumerate(workers):
                if worker.poll() is not None:
                    # Nobody killed this one: a worker that exits on a store
                    # error instead of abandoning the attempt is a defect.
                    died_alone.append(worker.returncode)
                    workers[index] = spawn()
            victim = rng.randrange(len(workers))
            workers[victim].kill()
            workers[victim].wait()
            kills += 1
            workers[victim] = spawn()
            if severable and rng.random() < 0.5:
                severed += await sever_connections(store_target, schema)
            if pending_shipments and rng.random() < 0.7:
                await deliver(pending_shipments.pop())
        for order in pending_shipments:
            await deliver(order)

        terminal_statuses = tuple(TERMINAL_RUN_STATUSES)
        drain_deadline = time.monotonic() + DRAIN_SECONDS
        while time.monotonic() < drain_deadline:
            total = await retrying(lambda: store.count_runs(RunQuery()))
            terminal = await retrying(
                lambda: store.count_runs(RunQuery(statuses=terminal_statuses))
            )
            if total == expected_runs and terminal == total:
                break
            await asyncio.sleep(0.25)
    finally:
        for worker in workers:
            worker.terminate()
        for worker in workers:
            worker.wait(timeout=30)

    runs = await retrying(lambda: store.list_runs(RunQuery(limit=500)))
    outcomes = Counter(run.status for run in runs)
    problems = [
        f"{run.workflow_id} {run.run_id[:8]} {run.status.value}: {run.error}"
        for run in runs
        if run.status is not RunStatus.COMPLETED
    ]
    worker_tail = "\n".join(
        f"--- {log.name}\n" + log.read_text()[-600:] for log in logs if log.exists()
    )
    assert died_alone == [], (
        f"workers exited on their own with {died_alone}; a store error must "
        f"abandon the attempt, not the process\n{worker_tail}"
    )
    assert len(runs) == expected_runs, (len(runs), expected_runs, worker_tail)
    assert outcomes == {RunStatus.COMPLETED: expected_runs}, (
        f"after {kills} kills:\n" + "\n".join(problems) + "\n" + worker_tail
    )

    ledger = Counter(effects())
    for order in payments:
        assert ledger[f"charge:{order}"] == 1, (
            order,
            "a guarded charge must happen once",
        )
        assert ledger[f"charge-attempt:{order}"] >= 1, (order, "never charged")
        assert ledger[f"settle:ch_{order}"] >= 1, (order, "settlement never landed")
        assert ledger[f"settle-flake:ch_{order}"] >= 2, (order, "the retry never ran")
    for order in shipments:
        assert ledger[f"close-attempt:{order}"] >= 1, (order, "never handled")
        assert ledger[f"close:{order}"] == 1, (order, "the provider saw one shipment")
    for order in rollouts:
        assert ledger[f"region:{order}:a"] == 1, (order, "guarded branch a once")
        assert ledger[f"region:{order}:b"] == 1, (order, "guarded branch b once")
    assert ledger["report"] >= len(rollouts)

    recovered = 0
    for run in runs:
        snapshot = await kernel.get_run(run.run_id)
        assert snapshot is not None
        if run.workflow_id == "chaos.shipment":
            # The handler may run twice; the signal must have reached the run
            # exactly once, whatever the kills did around it. It resolves the
            # wait directly when the wait was already armed, and is buffered
            # for the wait to consume on arming when it arrived first.
            arrivals = sum(
                1
                for event in await store.get_history(run.run_id)
                if event.type
                in (HistoryEventType.WAIT_RESOLVED, HistoryEventType.SIGNAL_BUFFERED)
            )
            assert arrivals == 1, (run.run_id, "one signal reaches the run once")
        assert all(step.status is not StepStatus.CLAIMED for step in snapshot.steps), (
            run.run_id,
            "a finished run holds no claim",
        )
        history = await store.get_history(run.run_id)
        recovered += sum(
            1 for event in history if event.type is HistoryEventType.STEP_RECOVERED
        )
    assert kills >= 3, f"only {kills} kills in {SECONDS}s; the soak proved little"
    if severable:
        assert severed >= 1, "no worker connection was ever severed"
    assert recovered >= 1, (
        f"{kills} kills landed on no held claim; the soak proved nothing about recovery"
    )

    await driver.shutdown()
    await _close_store(store)
