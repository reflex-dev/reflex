"""Tests that need a real PostgreSQL server.

The point of the Postgres store is the thing SQLite cannot do: several worker
processes claiming from one mailbox at the same time. These tests run two
kernels against one database and assert what a durable engine has to promise
under that load -- every run executes, and no run executes twice.

They are skipped unless ``REFLEX_TEST_POSTGRES`` names a server.
"""

import asyncio
import json
import os
import time
import uuid

import pytest
from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.definition import compile_workflow
from reflex.workflow.kernel import WorkflowKernel, WorkflowObserver
from reflex.workflow.records import (
    HistoryEventType,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
)

POSTGRES_URL = os.environ.get("REFLEX_TEST_POSTGRES") or ""

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="set REFLEX_TEST_POSTGRES to run Postgres tests"
)

EXECUTIONS: list[str] = []


@pytest.fixture(autouse=True)
def harness_store():
    """Opt out of the shared store parameter.

    These tests drive kernels against their own Postgres store, so running
    them once per store kind would just repeat the same work.

    Returns:
        The store kind this module uses.
    """
    return "postgres"


class Charge(rx.State):
    """A workflow whose one step must never run twice."""

    __workflow__ = WorkflowConfig(id="pg.charge")
    invoice: str = ""

    @rx.event(durable=True, trigger=manual(), effect="non_idempotent_write")
    async def start(self, invoice: str):
        """Charge the invoice exactly once.

        Args:
            invoice: The invoice identifier.

        Returns:
            Completion.
        """
        EXECUTIONS.append(invoice)
        await asyncio.sleep(0.01)
        self.invoice = invoice
        return rx.complete(result={"charged": invoice})


@pytest.fixture
async def store():
    """Open a Postgres store in a throwaway schema.

    The pool is closed on the test's own loop before the schema drops: a pool
    left open leaks worker tasks into loop teardown, where a task that
    catches its cancellation to clean up a connection is never cancelled a
    second time and can wait forever.

    Yields:
        The store.
    """
    from reflex.workflow.postgres import PostgresRunStore

    schema = f"wf_test_{uuid.uuid4().hex}"
    opened = PostgresRunStore(POSTGRES_URL, schema=schema, min_size=0, max_size=6)
    yield opened
    await opened.close()
    opened.drop_schema()


async def test_two_workers_share_one_mailbox_without_double_execution(store):
    """Two kernels on one database run every step exactly once.

    This is the claim SQLite cannot support and the reason the Postgres store
    exists. A step marked non_idempotent_write running twice is a double
    charge, so the assertion is exact, not statistical.
    """
    EXECUTIONS.clear()
    definition = compile_workflow(Charge)
    claimed: list[set[str]] = [set(), set()]

    def watcher(index: int):
        """Record which runs one worker started attempts on.

        Args:
            index: Which worker this observer belongs to.

        Returns:
            An observer for that worker.
        """

        class Watcher(WorkflowObserver):
            def on_event(self, event_type, run_id, workflow_id, data):
                """Note an attempt this worker started.

                Args:
                    event_type: The recorded transition.
                    run_id: The run it happened on.
                    workflow_id: The workflow identity.
                    data: The event payload.
                """
                if event_type is HistoryEventType.ATTEMPT_STARTED:
                    claimed[index].add(run_id)

        return Watcher()

    workers = [
        WorkflowKernel(
            [definition],
            store,
            poll_interval=0.01,
            max_concurrency=4,
            observer=watcher(index),
        )
        for index in range(2)
    ]

    invoices = [f"inv-{index}" for index in range(20)]
    for invoice in invoices:
        result = await workers[0].start(Charge.start(invoice))
        assert result.disposition == "started"

    for worker in workers:
        await worker.start_worker()
    try:
        for _ in range(500):
            runs = await workers[0].list_runs()
            if all(run.status is RunStatus.COMPLETED for run in runs) and len(
                runs
            ) == len(invoices):
                break
            await asyncio.sleep(0.02)
    finally:
        for worker in workers:
            await worker.aclose()

    assert sorted(EXECUTIONS) == sorted(invoices)
    runs = await workers[0].list_runs()
    assert len(runs) == len(invoices)
    assert {run.status for run in runs} == {RunStatus.COMPLETED}
    # Both workers pulled from the queue, and never the same run twice, so the
    # exactly-once result above is a real division of labour and not one
    # worker quietly doing everything.
    assert claimed[0]
    assert claimed[1]
    assert not claimed[0] & claimed[1]
    assert claimed[0] | claimed[1] == {run.run_id for run in runs}


async def test_a_second_worker_takes_over_an_abandoned_claim(store):
    """A worker that dies mid-step does not strand its run.

    The lease is what makes this safe: the survivor may only reclaim a step
    whose lease has lapsed, so recovery cannot race a worker that is merely
    slow.
    """
    EXECUTIONS.clear()
    definition = compile_workflow(Charge)
    dying = WorkflowKernel([definition], store, lease_duration=0.5)
    survivor = WorkflowKernel([definition], store, poll_interval=0.01, lease_duration=5)

    result = await dying.start(Charge.start("inv-orphan"))
    assert result.run_id is not None

    claim = await store.claim_next(time.time(), lease_duration=0.4)
    assert claim is not None
    assert claim.run.run_id == result.run_id

    # Nobody renews that lease, so it lapses as if the worker had died.
    await asyncio.sleep(0.6)
    assert await survivor.recover() == 1

    await survivor.start_worker()
    try:
        for _ in range(300):
            snapshot = await survivor.get_run(result.run_id)
            if snapshot is not None and snapshot.status is RunStatus.COMPLETED:
                break
            await asyncio.sleep(0.02)
    finally:
        await survivor.aclose()

    snapshot = await survivor.get_run(result.run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.COMPLETED
    assert EXECUTIONS == ["inv-orphan"]


async def test_concurrent_admissions_deduplicate_on_the_request_key(store):
    """A request key admitted from many workers at once yields one run.

    Postgres decides this with a unique index rather than a write lock, so it
    is the one place the two stores reach the same answer by different means.
    """
    definition = compile_workflow(Charge)
    workers = [
        WorkflowKernel([definition], store, poll_interval=0.01) for _ in range(4)
    ]
    results = await asyncio.gather(
        *(
            worker.start(Charge.start("inv-dupe"), request_key="webhook-1")
            for worker in workers
        )
    )
    run_ids = {result.run_id for result in results}
    assert len(run_ids) == 1
    assert sum(result.disposition == "started" for result in results) == 1
    assert sum(result.disposition == "deduplicated" for result in results) == 3


def test_the_cli_operates_on_a_postgres_url(store):
    """`reflex workflows` accepts a Postgres URL, not just a SQLite path.

    The commands each ran their own ``asyncio.run`` before this, which works
    for a file-backed store and fails for a pooled one: the pool's connections
    belong to the loop that opened them, so closing from a second loop raised.
    Only driving the real command surfaced it.
    """
    from click.testing import CliRunner

    from reflex.workflow.cli import workflows

    async def seed():
        """Admit one run directly, so the CLI has something to find."""
        now = time.time()
        await store.admit(
            RunRecord(
                run_id="cli-run",
                workflow_id="pg.charge",
                definition_digest="digest",
                status=RunStatus.RUNNING,
                state={},
                state_version=0,
                next_ordinal=1,
                labels={"team": "ops"},
                created_at=now,
                updated_at=now,
            ),
            StepRecord(
                run_id="cli-run",
                ordinal=0,
                handler_id="start",
                status=StepStatus.READY,
                args={},
                origin="root",
                created_at=now,
                updated_at=now,
            ),
            ((HistoryEventType.RUN_ADMITTED, {}),),
        )

    async def seed_and_close():
        """Seed on one loop and close the pool on that same loop.

        The fixture's teardown runs on a different loop, and a pool can only
        be closed from the loop that opened it.
        """
        await seed()
        await store.close()

    asyncio.run(seed_and_close())
    url = f"{POSTGRES_URL}?options=-csearch_path%3D{store.schema}"

    listed = CliRunner().invoke(workflows, ["list", "-d", url, "--json"])
    assert listed.exit_code == 0, listed.output
    assert [row["run_id"] for row in json.loads(listed.output)] == ["cli-run"]

    shown = CliRunner().invoke(workflows, ["show", "cli-run", "-d", url])
    assert shown.exit_code == 0, shown.output
    assert "pg.charge" in shown.output

    cancelled = CliRunner().invoke(workflows, ["cancel", "cli-run", "-d", url])
    assert cancelled.exit_code == 0, cancelled.output


async def test_closing_a_parent_never_deadlocks_against_its_children(store):
    """Cancel a fan-out while its branches report home, repeatedly.

    Closing a parent touches the parent and then its children; a child
    reporting home touches itself and then its parent. Same two rows,
    opposite orders -- Postgres detects the cycle and aborts one side, and
    before the lock ordering was fixed this produced deadlocks on most
    rounds. Recovery did eventually converge, but sometimes only after a
    lease lapsed, which is half a minute of a cancelled rollout still
    running.

    Args:
        store: The Postgres store.
    """
    rounds, branches = 12, 6
    failures: list[str] = []
    for index in range(rounds):
        parent = f"dlp{index}"
        kids = [f"dlk{index}_{n}" for n in range(branches)]
        await store.admit(
            _pg_run(parent, next_ordinal=2),
            _pg_step(parent, 1, status=StepStatus.BLOCKED, wait_key="join:1"),
            _PG_ADMITTED,
        )
        for kid in kids:
            await store.admit(
                _pg_run(kid, parent_run_id=parent, parent_ordinal=1),
                _pg_step(kid),
                _PG_ADMITTED,
            )

        async def close_parent(parent=parent):
            """Cancel the parent, closing its branches.

            Args:
                parent: The parent run.
            """
            await store.request_cancel(parent, _PG_NOW)
            await store.finalize_run(
                parent,
                status=RunStatus.CANCELLED,
                error=None,
                event=HistoryEventType.RUN_CANCELLED,
                now=_PG_NOW,
            )

        async def report(kid: str, parent=parent):
            """Finish a branch, delivering its arrival.

            Args:
                kid: The branch run.
                parent: The parent run.
            """
            await store.finalize_run(
                kid,
                status=RunStatus.COMPLETED,
                error=None,
                event=HistoryEventType.RUN_COMPLETED,
                now=_PG_NOW,
                parent_arrival=(parent, 1, {"status": "completed"}, kid),
            )

        outcomes = await asyncio.gather(
            close_parent(), *(report(kid) for kid in kids), return_exceptions=True
        )
        failures.extend(
            type(outcome).__name__
            for outcome in outcomes
            if isinstance(outcome, BaseException)
        )
    assert not failures, f"{len(failures)} transaction(s) aborted: {set(failures)}"


_PG_NOW = 1_000_000.0
_PG_ADMITTED = ((HistoryEventType.RUN_ADMITTED, {}),)


def _pg_run(run_id: str, **over) -> RunRecord:
    """Build a run record for the deadlock probe.

    Args:
        run_id: The run identity.
        over: Field overrides.

    Returns:
        The record.
    """
    fields: dict = {
        "run_id": run_id,
        "workflow_id": "pg.deadlock",
        "definition_digest": "d",
        "status": RunStatus.PENDING,
        "state": {},
        "state_version": 0,
        "next_ordinal": 2,
        "created_at": _PG_NOW,
        "updated_at": _PG_NOW,
    }
    fields.update(over)
    return RunRecord(**fields)


def _pg_step(run_id: str, ordinal: int = 0, **over) -> StepRecord:
    """Build a step record for the deadlock probe.

    Args:
        run_id: The owning run.
        ordinal: The mailbox position.
        over: Field overrides.

    Returns:
        The record.
    """
    fields: dict = {
        "run_id": run_id,
        "ordinal": ordinal,
        "handler_id": "go",
        "status": StepStatus.READY,
        "args": {},
        "origin": "root",
        "created_at": _PG_NOW,
        "updated_at": _PG_NOW,
    }
    fields.update(over)
    return StepRecord(**fields)


async def test_twelve_workers_can_initialize_a_fresh_schema_together():
    """First deploy of a fleet: every worker races the same CREATE statements.

    IF NOT EXISTS does not make concurrent DDL safe -- each CREATE TABLE also
    inserts the table's composite type, and two backends that both saw "not
    exists" race on pg_type. Twelve fresh workers produced one winner and
    eleven UniqueViolations, so a fleet's first deploy crash-looped everyone
    but one. The advisory lock serializes initializers; this drives twelve
    concurrent stores at one brand-new schema and requires them all to come
    up.
    """
    from reflex.workflow.postgres import PostgresRunStore

    schema = f"initrace_{uuid.uuid4().hex[:12]}"
    stores = [
        PostgresRunStore(POSTGRES_URL, schema=schema, min_size=0, max_size=2)
        for _ in range(12)
    ]
    try:
        outcomes = await asyncio.gather(
            *(store.epoch_time() for store in stores), return_exceptions=True
        )
        errors = [o for o in outcomes if isinstance(o, BaseException)]
        assert not errors, f"{len(errors)} of 12 initializers failed: {errors[:2]}"
    finally:
        for store in stores:
            await store.close()
        stores[0].drop_schema()
