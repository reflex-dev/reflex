"""The SQLite scheduler surface must answer from an index, not a Python loop.

An idle worker polls ``next_due`` and ``claim_next`` continuously. Loading
every active run and walking its steps in Python made both linear in the
number of sleeping runs: at ten thousand durable timers an external review
measured ~114ms per poll, 31-50% CPU on a worker with nothing to do, and a
quadratic-looking burst drain. The queries now filter by wake-ability through
``idx_workflow_steps_wake`` first and pay the frontier check only for
candidates, which the same setup measures at well under five milliseconds.
"""

import uuid

from reflex.workflow.records import RunRecord, RunStatus, StepRecord, StepStatus
from reflex.workflow.store import SqliteRunStore, _sqlite_frontier_query

NOW = 1_000_000.0


def _sleeper(index: int, due_at: float, status: StepStatus = StepStatus.READY):
    """Build one waiting run and its frontier slot.

    Args:
        index: Uniquifies the run.
        due_at: When the frontier comes due.
        status: The frontier's status.

    Returns:
        The run record and its step.
    """
    run_id = f"run{index:05d}{uuid.uuid4().hex[:6]}"
    run = RunRecord(
        run_id=run_id,
        workflow_id="frontier.bench",
        definition_digest="d",
        status=RunStatus.WAITING,
        state={},
        state_version=1,
        next_ordinal=2,
        created_at=NOW + index,
        updated_at=NOW,
    )
    step = StepRecord(
        run_id=run_id,
        ordinal=1,
        handler_id="wake",
        status=status,
        args={},
        due_at=due_at,
        origin="root",
        queue="default",
        created_at=NOW,
        updated_at=NOW,
    )
    return run, step


async def test_the_frontier_queries_use_the_wake_index(tmp_path):
    """The plan is the performance contract; pin it so it cannot rot.

    A timing assertion flakes on shared CI; the query plan does not. If
    either query stops using the wake index, an idle worker is back to
    scanning every sleeping run per poll.
    """
    store = SqliteRunStore(tmp_path / "plan.db")
    run, step = _sleeper(0, NOW + 86_400)
    await store.admit(run, step, ())
    for due_only in (True, False):
        sql, params = _sqlite_frontier_query(
            "s.*", NOW, None, due_only=due_only, order="s.due_at", limit=1
        )
        plan = " ".join(
            row["detail"]
            for row in store._db.execute(  # pyright: ignore[reportPrivateUsage]
                f"EXPLAIN QUERY PLAN {sql}", params
            ).fetchall()
        )
        assert "idx_workflow_steps_wake" in plan, plan
    store.close()


async def test_a_due_run_is_found_among_ten_thousand_sleepers(tmp_path):
    """Scale changes the cost, never the answer."""
    store = SqliteRunStore(tmp_path / "mixed.db")
    for index in range(500):
        run, step = _sleeper(index, NOW + 86_400 + index)
        await store.admit(run, step, ())
    due_run, due_step = _sleeper(9_999, NOW - 5)
    await store.admit(due_run, due_step, ())

    assert await store.next_due(NOW) is not None
    claim = await store.claim_next(NOW)
    assert claim is not None
    assert claim.run.run_id == due_run.run_id, (
        "the one due run must be claimed, not any of the sleepers"
    )
    assert await store.claim_next(NOW) is None, "nothing else is due"
    due = await store.next_due(NOW)
    assert due is not None
    assert abs(due - (NOW + 86_400)) < 1e-6, "the earliest sleeper is the next wake"
    store.close()


def test_a_future_schema_stamp_is_never_downgraded(tmp_path):
    """An older binary must not restamp a newer schema as its own.

    Newer schemas are additive by policy, so reading one is safe -- but
    rerunning this binary's DDL would overwrite the newer version stamp with
    the older one, and the newer binary would then re-migrate a database that
    is already ahead of it.
    """
    from reflex.workflow.store import SCHEMA_VERSION

    path = tmp_path / "future.db"
    store = SqliteRunStore(path)
    assert store._db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION  # pyright: ignore[reportPrivateUsage]
    store._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 7}")  # pyright: ignore[reportPrivateUsage]
    store.close()

    reopened = SqliteRunStore(path)
    stamp = reopened._db.execute("PRAGMA user_version").fetchone()[0]  # pyright: ignore[reportPrivateUsage]
    assert stamp == SCHEMA_VERSION + 7, "the newer stamp was downgraded"
    reopened.close()
