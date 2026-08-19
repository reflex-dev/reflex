"""Start policies must hold across processes, not just across tasks.

Every policy is a read followed by a write. The old design guarded the gap
with an in-process asyncio lock, which meant two worker processes admitting
concurrently both read "nothing active yet" and both inserted: in an external
review, all five policy families violated their invariant in 50 out of 50
synchronized trials across two OS processes and independent PostgreSQL pools.

These tests open two *independent store instances* on one database -- two
pools, two connections, no shared Python state, which is what two processes
look like to the database -- and race gated admissions through both. The
invariants must hold because the store serializes the whole decision under a
durable per-key lock, not because anything in this process arranged politeness.
"""

import asyncio
import dataclasses
import os
import uuid
from collections.abc import AsyncIterator

import pytest

from reflex.workflow.records import RunRecord, RunStatus, StepRecord, StepStatus
from reflex.workflow.store import FlowGate, RunStore, SqliteRunStore

TRIALS = 10
POSTGRES_ENV = "REFLEX_TEST_POSTGRES"


@pytest.fixture(params=["sqlite", "postgres"])
async def store_pair(request, tmp_path) -> AsyncIterator[tuple[RunStore, RunStore]]:
    """Two store instances over one database, like two worker processes.

    Args:
        request: The backend under test.
        tmp_path: Directory for the SQLite file.

    Yields:
        Two independently connected stores sharing one database.
    """
    if request.param == "sqlite":
        path = tmp_path / "race.db"
        a, b = SqliteRunStore(path), SqliteRunStore(path)
        yield a, b
        a.close()
        b.close()
        return
    dsn = os.environ.get(POSTGRES_ENV)
    if not dsn:
        pytest.skip(f"{POSTGRES_ENV} is not configured")
    from reflex.workflow.postgres import PostgresRunStore
    from reflex.workflow.records import RunQuery

    schema = f"flowrace_{uuid.uuid4().hex[:12]}"
    a = PostgresRunStore(dsn, schema=schema)
    b = PostgresRunStore(dsn, schema=schema)
    # Migration is lazy on first use; racing it from two fresh stores is a
    # CREATE TABLE collision, not the admission race under test.
    await a.list_runs(RunQuery(limit=1))
    yield a, b
    await b.close()
    await a.close()
    a.drop_schema()


def _records(flow_key: str, args: dict | None = None) -> tuple[RunRecord, StepRecord]:
    """Build one admission's records under a flow key.

    Args:
        flow_key: The policy grouping key.
        args: Root payload, when the test cares about it.

    Returns:
        The run record and its root slot.
    """
    run_id = uuid.uuid4().hex
    now = 1_000_000.0
    run = RunRecord(
        run_id=run_id,
        workflow_id="race.flow",
        definition_digest="digest",
        status=RunStatus.PENDING,
        state={},
        state_version=0,
        next_ordinal=1,
        flow_key=flow_key,
        created_at=now,
        updated_at=now,
    )
    step = StepRecord(
        run_id=run_id,
        ordinal=0,
        handler_id="start",
        status=StepStatus.READY,
        args=args or {},
        due_at=now,
        origin="root",
        queue="default",
        created_at=now,
        updated_at=now,
    )
    return run, step


async def _race(a: RunStore, b: RunStore, gate: FlowGate, key: str, args=None) -> list:
    """Admit through both stores at once.

    Args:
        a: The first store instance.
        b: The second store instance.
        gate: The policy under test.
        key: The flow key for this trial.
        args: Optional distinct payloads for the two admissions.

    Returns:
        Both admission outcomes.
    """

    async def admit(store: RunStore, payload):
        """Run one gated admission.

        Args:
            store: The store to admit through.
            payload: The root payload.

        Returns:
            The admission outcome.
        """
        run, step = _records(key, payload)
        return await store.admit_flow(run, step, (), gate, 1_000_000.0)

    first, second = args or ({}, {})
    return list(await asyncio.gather(admit(a, first), admit(b, second)))


async def test_singleton_skip_admits_exactly_one(store_pair):
    """Two processes racing a singleton must not both win it."""
    a, b = store_pair
    for trial in range(TRIALS):
        outcomes = await _race(a, b, FlowGate(singleton_skip=True), f"skip-{trial}")
        dispositions = sorted(o.disposition for o in outcomes)
        assert dispositions == ["skipped", "started"], f"trial {trial}: {dispositions}"
        started = next(o for o in outcomes if o.disposition == "started")
        skipped = next(o for o in outcomes if o.disposition == "skipped")
        assert skipped.run_id == started.run_id, (
            "the loser must be told which run holds the key"
        )


async def test_rate_limit_of_one_admits_exactly_one(store_pair):
    """A limit of one is a limit of one from any number of processes."""
    a, b = store_pair
    for trial in range(TRIALS):
        outcomes = await _race(a, b, FlowGate(rate_limit=(1, 60.0)), f"rate-{trial}")
        dispositions = sorted(o.disposition for o in outcomes)
        assert dispositions == ["rejected", "started"], f"trial {trial}: {dispositions}"


async def test_debounce_coalesces_the_racing_start(store_pair):
    """One of a racing pair is absorbed by the other, never two runs."""
    a, b = store_pair
    for trial in range(TRIALS):
        outcomes = await _race(
            a,
            b,
            FlowGate(debounce=30.0),
            f"deb-{trial}",
            args=({"revision": 1}, {"revision": 2}),
        )
        dispositions = sorted(o.disposition for o in outcomes)
        assert dispositions == ["coalesced", "started"], (
            f"trial {trial}: {dispositions}"
        )
        started = next(o for o in outcomes if o.disposition == "started")
        coalesced = next(o for o in outcomes if o.disposition == "coalesced")
        assert coalesced.run_id == started.run_id
        # Latest wins: whichever admission lost the race replaced the payload.
        steps = await a.get_steps(started.run_id)
        assert steps[0].args in ({"revision": 1}, {"revision": 2})


async def test_throttle_of_one_spaces_the_racing_pair(store_pair):
    """Both start, but the second sits a full window after the first."""
    a, b = store_pair
    for trial in range(TRIALS):
        outcomes = await _race(a, b, FlowGate(throttle=(1, 60.0)), f"thr-{trial}")
        assert all(o.disposition == "started" for o in outcomes)
        dues = sorted([(await a.get_steps(o.run_id))[0].due_at for o in outcomes])
        assert dues[1] - dues[0] >= 60.0 - 1e-9, (
            f"trial {trial}: both roots due at {dues}; the burst was not spaced"
        )


async def test_singleton_cancel_leaves_at_most_one_uncancelled(store_pair):
    """Racing replacements never leave two live runs on the key."""
    a, b = store_pair
    for trial in range(TRIALS):
        key = f"cxl-{trial}"
        outcomes = await _race(a, b, FlowGate(singleton_cancel=True), key)
        assert all(o.disposition == "started" for o in outcomes)
        live = [
            o.run_id
            for o in outcomes
            if (run := await a.get_run(o.run_id)) is not None
            and not run.cancel_requested
        ]
        assert len(live) <= 1, (
            f"trial {trial}: {len(live)} replacements survived on one key"
        )


async def test_gated_dedupe_is_atomic_across_instances(store_pair):
    """A redelivered event admitted through the gate is still one run."""
    a, b = store_pair
    for trial in range(TRIALS):
        key = f"ded-{trial}"

        async def admit(store: RunStore, key: str = key):
            """Admit one redelivery of the same event.

            Args:
                store: The store to admit through.
                key: The flow key for this trial.

            Returns:
                The admission outcome.
            """
            run, step = _records(key)
            run = dataclasses.replace(run, request_key=f"evt-{key}")
            return await store.admit_flow(
                run, step, (), FlowGate(singleton_skip=True), 1_000_000.0
            )

        outcomes = list(await asyncio.gather(admit(a), admit(b)))
        dispositions = sorted(o.disposition for o in outcomes)
        assert dispositions == ["deduplicated", "started"], (
            f"trial {trial}: {dispositions}"
        )


async def test_a_duplicate_under_a_different_flow_key_mutates_nothing(store_pair):
    """A duplicate admission must leave with zero side effects.

    Two admissions can share a request key while computing different flow
    keys -- different advisory locks -- so the loser's dedupe check is not
    serialized against the winner. If the dedupe reservation came after the
    policy mutations, the duplicate would cancel the OTHER flow key's
    incumbent and commit that cancellation on its way out as "deduplicated":
    an unrelated live run killed by an event that had already been handled.
    """
    a, b = store_pair
    for trial in range(TRIALS):
        # A live incumbent on flow key B that nothing should ever touch.
        incumbent, incumbent_step = _records(f"other-{trial}")
        assert (
            await a.admit_flow(
                incumbent,
                incumbent_step,
                (),
                FlowGate(singleton_cancel=True),
                1_000_000.0,
            )
        ).disposition == "started"

        async def admit(store: RunStore, key: str, trial: int = trial):
            """Admit one delivery of the shared event.

            Args:
                store: The store to admit through.
                key: This admission's flow key.
                trial: The trial number.

            Returns:
                The admission outcome.
            """
            run, step = _records(key)
            run = dataclasses.replace(run, request_key=f"shared-{trial}")
            return await store.admit_flow(
                run, step, (), FlowGate(singleton_cancel=True), 1_000_000.0
            )

        mine_outcome, other_outcome = await asyncio.gather(
            admit(a, f"mine-{trial}"), admit(b, f"other-{trial}")
        )
        dispositions = sorted([mine_outcome.disposition, other_outcome.disposition])
        assert dispositions == ["deduplicated", "started"], (
            f"trial {trial}: {dispositions}"
        )
        survivor = await a.get_run(incumbent.run_id)
        assert survivor is not None
        if other_outcome.disposition == "deduplicated":
            # The admission on the incumbent's flow key lost the dedupe race,
            # so it decided nothing: the incumbent must be untouched.
            assert not survivor.cancel_requested, (
                f"trial {trial}: a duplicate cancelled an unrelated incumbent"
            )
            assert other_outcome.cancelled == ()
