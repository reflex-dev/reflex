"""Tests for the workflow run stores."""

import pytest

from reflex.workflow.records import (
    HistoryEventType,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
)
from reflex.workflow.store import (
    MemoryRunStore,
    SqliteRunStore,
    StaleClaimError,
    StepCompletion,
)

NOW = 1_000_000.0


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    """A run store of each implementation.

    Args:
        request: The fixture request carrying the store kind.
        tmp_path: Temporary directory for the SQLite database.

    Yields:
        The store instance.
    """
    if request.param == "memory":
        yield MemoryRunStore()
    else:
        sqlite_store = SqliteRunStore(tmp_path / "workflow.db")
        yield sqlite_store
        sqlite_store.close()


def _run(run_id: str = "run1", **overrides) -> RunRecord:
    defaults = {
        "run_id": run_id,
        "workflow_id": "billing.store_test",
        "definition_digest": "digest",
        "status": RunStatus.PENDING,
        "state": {"n": 0},
        "state_version": 0,
        "next_ordinal": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return RunRecord(**defaults)


def _step(run_id: str = "run1", ordinal: int = 0, **overrides) -> StepRecord:
    defaults = {
        "run_id": run_id,
        "ordinal": ordinal,
        "handler_id": "go",
        "status": StepStatus.READY,
        "args": {},
        "origin": "root",
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return StepRecord(**defaults)


_ADMIT_EVENTS = ((HistoryEventType.RUN_ADMITTED, {}),)


async def test_admit_and_load_round_trip(store):
    created, run_id = await store.admit(
        _run(request_key="key1", labels={"customer": "c1"}), _step(), _ADMIT_EVENTS
    )
    assert created
    assert run_id == "run1"
    run = await store.get_run("run1")
    assert run is not None
    assert run.state == {"n": 0}
    assert run.labels == {"customer": "c1"}
    steps = await store.get_steps("run1")
    assert [step.status for step in steps] == [StepStatus.READY]
    history = await store.get_history("run1")
    assert [event.type for event in history] == [HistoryEventType.RUN_ADMITTED]
    assert history[0].seq == 1


async def test_admit_deduplicates_on_request_key(store):
    await store.admit(_run(request_key="key1"), _step(), _ADMIT_EVENTS)
    created, run_id = await store.admit(
        _run(run_id="run2", request_key="key1"), _step(run_id="run2"), _ADMIT_EVENTS
    )
    assert not created
    assert run_id == "run1"
    assert await store.get_run("run2") is None


async def test_claim_respects_frontier_and_due_time(store):
    await store.admit(_run(next_ordinal=3), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.RUNNING,
            state={"n": 1},
            new_steps=(
                _step(ordinal=1, handler_id="second", due_at=NOW + 60, origin="delay"),
                _step(ordinal=2, handler_id="third", origin="chain"),
            ),
            next_ordinal=3,
        ),
        NOW,
    )
    # Ordinal 1 is the frontier but not due yet; ordinal 2 must not overtake it.
    assert await store.claim_next(NOW) is None
    assert await store.next_due(NOW) == NOW + 60
    claim = await store.claim_next(NOW + 61)
    assert claim is not None
    assert claim.step.ordinal == 1
    assert claim.step.handler_id == "second"


async def test_commit_bumps_state_version_and_fences(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.RETRY_WAIT,
            run_status=RunStatus.RETRYING,
            state=None,
            consume_attempt=True,
            due_at=NOW + 5,
        ),
        NOW,
    )
    run = await store.get_run("run1")
    assert run is not None
    assert run.state_version == 0
    steps = await store.get_steps("run1")
    assert steps[0].attempts == 1
    assert steps[0].status is StepStatus.RETRY_WAIT
    second_claim = await store.claim_next(NOW + 6)
    assert second_claim is not None
    assert second_claim.step.epoch == 2
    # The first claim is now stale and must not commit.
    with pytest.raises(StaleClaimError):
        await store.commit(
            claim,
            StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.COMPLETED,
                state={"n": 99},
            ),
            NOW + 7,
        )
    await store.commit(
        second_claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.COMPLETED,
            state={"n": 2},
        ),
        NOW + 7,
    )
    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.COMPLETED
    assert run.state == {"n": 2}
    assert run.state_version == 1


async def test_release_claim_returns_step(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW)
    assert claim is not None
    await store.release_claim(
        claim,
        status=StepStatus.CANCELLED,
        events=((HistoryEventType.ATTEMPT_CANCELLED, {"ordinal": 0}),),
        now=NOW,
    )
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.CANCELLED
    # Releasing again is a no-op because the claim is stale.
    await store.release_claim(claim, status=StepStatus.READY, events=(), now=NOW)
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.CANCELLED


async def test_cancel_control_and_finalize(store):
    await store.admit(_run(next_ordinal=2), _step(), _ADMIT_EVENTS)
    assert await store.control_pending(NOW) == ()
    assert await store.request_cancel("run1", NOW)
    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.CANCELLING
    pending = await store.control_pending(NOW)
    assert [run.run_id for run in pending] == ["run1"]
    assert await store.finalize_run(
        "run1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW,
    )
    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.CANCELLED
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.CANCELLED
    history = await store.get_history("run1")
    assert history[-1].type is HistoryEventType.RUN_CANCELLED
    assert HistoryEventType.STEP_TOMBSTONED in [event.type for event in history]
    # A terminal run cannot be cancelled or finalized again.
    assert not await store.request_cancel("run1", NOW)
    assert not await store.finalize_run(
        "run1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW,
    )


async def test_finalize_refused_while_claimed(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW)
    assert claim is not None
    await store.request_cancel("run1", NOW)
    assert await store.control_pending(NOW) == ()
    assert not await store.finalize_run(
        "run1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW,
    )


async def test_deadline_makes_run_control_pending(store):
    await store.admit(_run(deadline=NOW + 100), _step(due_at=NOW + 500), _ADMIT_EVENTS)
    assert await store.control_pending(NOW) == ()
    assert await store.claim_next(NOW + 200) is None
    pending = await store.control_pending(NOW + 200)
    assert [run.run_id for run in pending] == ["run1"]


async def test_recover_orphans_consumes_recovery_budget(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=5.0)
    assert claim is not None
    recovered, _ = await store.recover_orphans(NOW + 10, max_recoveries=2)
    assert recovered == 1
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.RECOVERY_WAIT
    assert steps[0].recoveries == 1
    # The stale claim cannot commit after recovery.
    with pytest.raises(StaleClaimError):
        await store.commit(
            claim,
            StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.COMPLETED,
                state={},
            ),
            NOW + 11,
        )


async def test_recover_orphans_exhaustion_fails_run(store):
    await store.admit(_run(), _step(recoveries=2), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=5.0)
    assert claim is not None
    await store.recover_orphans(NOW + 10, max_recoveries=2)
    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.error == {"reason": "recovery_budget_exhausted"}


async def test_append_events_assigns_sequence(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    await store.append_events(
        "run1", ((HistoryEventType.ATTEMPT_STARTED, {"ordinal": 0}),), NOW
    )
    history = await store.get_history("run1")
    assert [event.seq for event in history] == [1, 2]
    assert history[-1].type is HistoryEventType.ATTEMPT_STARTED


async def test_sqlite_persistence_across_reopen(tmp_path):
    db_path = tmp_path / "workflow.db"
    first = SqliteRunStore(db_path)
    await first.admit(_run(request_key="key1"), _step(), _ADMIT_EVENTS)
    claim = await first.claim_next(NOW, lease_duration=1.0)
    assert claim is not None
    first.close()

    second = SqliteRunStore(db_path)
    try:
        run = await second.get_run("run1")
        assert run is not None
        steps = await second.get_steps("run1")
        assert steps[0].status is StepStatus.CLAIMED
        # Dedupe state survives restarts.
        created, run_id = await second.admit(
            _run(run_id="run2", request_key="key1"),
            _step(run_id="run2"),
            _ADMIT_EVENTS,
        )
        assert not created
        assert run_id == "run1"
        # The orphaned claim recovers on the new process.
        assert (await second.recover_orphans(NOW + 5, max_recoveries=10))[0] == 1
        steps = await second.get_steps("run1")
        assert steps[0].status is StepStatus.RECOVERY_WAIT
    finally:
        second.close()


async def test_claim_sets_a_lease(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    assert claim.step.lease_expires_at == pytest.approx(NOW + 30.0)
    steps = await store.get_steps("run1")
    assert steps[0].lease_expires_at == pytest.approx(NOW + 30.0)


async def test_renew_lease_extends_the_expiry(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    assert await store.renew_lease(claim, NOW + 10.0, lease_duration=30.0)
    steps = await store.get_steps("run1")
    assert steps[0].lease_expires_at == pytest.approx(NOW + 40.0)
    # Renewal is a liveness signal only: it transitions nothing.
    assert steps[0].status is StepStatus.CLAIMED
    assert steps[0].epoch == claim.step.epoch
    assert steps[0].attempts == 0
    assert steps[0].recoveries == 0
    # The renewed claim still commits.
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.COMPLETED,
            state={"n": 1},
        ),
        NOW + 11.0,
    )
    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.COMPLETED


async def test_recover_orphans_skips_unexpired_leases(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    assert (await store.recover_orphans(NOW + 29.0, max_recoveries=10))[0] == 0
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.CLAIMED
    assert steps[0].recoveries == 0


async def test_recover_orphans_reclaims_at_the_expiry_boundary(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    assert (await store.recover_orphans(NOW + 30.0, max_recoveries=10))[0] == 1
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.RECOVERY_WAIT
    assert steps[0].recoveries == 1
    # Lease loss is infrastructure, never a business attempt.
    assert steps[0].attempts == 0
    assert steps[0].lease_expires_at == pytest.approx(0.0)
    with pytest.raises(StaleClaimError):
        await store.commit(
            claim,
            StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.COMPLETED,
                state={"n": 9},
            ),
            NOW + 31.0,
        )


async def test_renewed_lease_survives_a_later_sweep(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    assert await store.renew_lease(claim, NOW + 20.0, lease_duration=30.0)
    assert (await store.recover_orphans(NOW + 40.0, max_recoveries=10))[0] == 0
    assert (await store.recover_orphans(NOW + 50.0, max_recoveries=10))[0] == 1


async def test_renew_lease_refused_after_recovery(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=5.0)
    assert claim is not None
    assert (await store.recover_orphans(NOW + 10.0, max_recoveries=10))[0] == 1
    assert not await store.renew_lease(claim, NOW + 11.0, lease_duration=30.0)


async def test_renew_lease_refused_after_commit(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.COMPLETED,
            state={"n": 1},
        ),
        NOW + 1.0,
    )
    assert not await store.renew_lease(claim, NOW + 2.0, lease_duration=30.0)
    steps = await store.get_steps("run1")
    assert steps[0].lease_expires_at == pytest.approx(0.0)


async def test_release_claim_clears_the_lease(store):
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    await store.release_claim(claim, status=StepStatus.READY, events=(), now=NOW + 1.0)
    steps = await store.get_steps("run1")
    assert steps[0].lease_expires_at == pytest.approx(0.0)


async def test_sqlite_migrates_a_database_without_the_lease_column(tmp_path):
    db_path = tmp_path / "legacy.db"
    store = SqliteRunStore(db_path)
    await store.admit(_run(), _step(), _ADMIT_EVENTS)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    # Simulate a database written by a build that predates leases.
    store._db.execute("DROP INDEX IF EXISTS idx_workflow_steps_lease")
    store._db.execute("ALTER TABLE workflow_steps DROP COLUMN lease_expires_at")
    # A database written by an older build carries no schema-version stamp,
    # which is what tells the next open to run DDL at all.
    store._db.execute("PRAGMA user_version = 0")
    store.close()

    reopened = SqliteRunStore(db_path)
    try:
        steps = await reopened.get_steps("run1")
        assert steps[0].status is StepStatus.CLAIMED
        # A claim left by the previous binary has no lease, so it is a genuine
        # orphan and is reclaimed on the first sweep.
        assert steps[0].lease_expires_at == pytest.approx(0.0)
        assert (await reopened.recover_orphans(NOW, max_recoveries=10))[0] == 1
    finally:
        reopened.close()
    # Reopening an already-migrated database is a no-op.
    again = SqliteRunStore(db_path)
    again.close()
