"""Kill a real worker at a real boundary and hold the contract to its word.

The rest of the suite simulates crashes in-process -- abandoning a claim,
expiring a lease, committing behind a fence. That is a fair test of the
store's logic and no test at all of what actually reached the disk, because
the process that was supposed to have died is still there to tidy up.

These send SIGKILL to a separate process: no unwinding, no ``atexit``, no
final flush, nothing the kernel could have done "on the way down" because
there is no way down. A fresh process then opens the same database and has to
produce the outcome CONTRACT.md documents. Every scenario asserts against a
durable ledger that is fsynced before each crash, so an effect that really
happened can never be lost in a way that flatters the result.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

WORKER = Path(__file__).parent / "crash_worker.py"

LEASE_LAPSE = 1.4


@pytest.fixture(autouse=True)
def harness_store():
    """Opt out of the shared harness store parameter.

    These drive subprocesses against their own SQLite file, so running each
    one per store kind would repeat the same work with the same store.

    Returns:
        The store kind this module uses.
    """
    return "sqlite"


@pytest.fixture
def crash(tmp_path):
    """Give a test a database, a ledger, and a way to run the worker.

    Args:
        tmp_path: The test's temporary directory.

    Returns:
        A ``(phase, crash_at) -> CompletedProcess`` runner, with ``.ledger``
        and ``.db`` paths attached.
    """
    db = tmp_path / "crash.db"
    ledger = tmp_path / "ledger.txt"

    def run(
        phase: str, crash_at: str = "none", **env: str
    ) -> subprocess.CompletedProcess:
        """Run one phase of the worker.

        Args:
            phase: Which scenario the worker should drive.
            crash_at: The boundary at which it should die.
            env: Extra environment for the worker, such as its release id or
                how far its clock has moved on.

        Returns:
            The finished process.
        """
        return subprocess.run(
            [sys.executable, str(WORKER), str(db), str(ledger), phase],
            env={
                **os.environ,
                "CRASH_LEDGER": str(ledger),
                "CRASH_AT": crash_at,
                **env,
            },
            capture_output=True,
            timeout=120,
            check=False,
        )

    run.ledger = ledger  # pyright: ignore[reportFunctionMemberAccess]
    run.db = db  # pyright: ignore[reportFunctionMemberAccess]
    return run


def effects(ledger: Path) -> list[str]:
    """Read the durable record of what really ran.

    Args:
        ledger: The ledger file.

    Returns:
        One entry per side effect that happened, in order.
    """
    if not ledger.exists():
        return []
    return ledger.read_text().split()


def runs(db: Path) -> dict[str, str]:
    """Read run statuses straight out of the database.

    Args:
        db: The SQLite file.

    Returns:
        Run id to status, read without going through the store.
    """
    import sqlite3

    connection = sqlite3.connect(db)
    try:
        return {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT run_id, status FROM workflow_runs"
            ).fetchall()
        }
    finally:
        connection.close()


def query(db: Path, sql: str) -> list[tuple]:
    """Read rows straight out of the database, bypassing the store.

    Args:
        db: The SQLite file.
        sql: The query.

    Returns:
        The rows.
    """
    import sqlite3

    connection = sqlite3.connect(db)
    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def history_count(db: Path, event_type: str) -> int:
    """Count one kind of history event across every run.

    Args:
        db: The SQLite file.
        event_type: The event type's value.

    Returns:
        How many were recorded.
    """
    ((count,),) = query(
        db, f"SELECT COUNT(*) FROM workflow_history WHERE type = '{event_type}'"
    )
    return count


def assert_finished(finished: subprocess.CompletedProcess) -> None:
    """Confirm a recovering worker ran to completion.

    Args:
        finished: The finished process.
    """
    assert finished.returncode == 0, finished.stderr.decode()[-800:]


def assert_killed(finished: subprocess.CompletedProcess) -> None:
    """Confirm the worker really was killed rather than exiting.

    A scenario whose worker exited cleanly proves nothing, and would pass
    every assertion that follows.

    Args:
        finished: The finished process.
    """
    assert finished.returncode == -9, (
        f"expected SIGKILL, got {finished.returncode}: {finished.stderr.decode()[-800:]}"
    )


def test_a_crash_before_the_effect_costs_nothing(crash):
    """Dying between claim and handler leaves the work simply undone.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("unguarded", "after_claim"))
    assert effects(crash.ledger) == []

    time.sleep(LEASE_LAPSE)
    assert crash("recover").returncode == 0
    assert effects(crash.ledger) == ["unguarded"], "recovery must run it exactly once"


def test_an_unguarded_effect_is_at_least_once_as_documented(crash):
    """Section 2 promises re-execution, and this is what that costs.

    Not a bug being pinned as behaviour: it is the reason ``rx.step`` exists,
    and the number here is what a workflow author is choosing to accept by
    calling a provider without one.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("unguarded", "after_effect"))
    assert effects(crash.ledger) == ["unguarded"]

    time.sleep(LEASE_LAPSE)
    assert crash("recover").returncode == 0
    assert effects(crash.ledger) == ["unguarded", "unguarded"], (
        "an unguarded effect repeats after a crash; that is the contract"
    )


def test_a_journalled_effect_survives_a_real_kill_exactly_once(crash):
    """The substep journal's whole promise, against a real process death.

    The charge is made, the journal records it, and the process is killed
    before anything commits. The recovered attempt must replay the recorded
    charge rather than make it again, because the money already moved.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("guarded", "after_step_record"))
    assert effects(crash.ledger) == ["guarded"]

    time.sleep(LEASE_LAPSE)
    assert crash("recover").returncode == 0
    assert effects(crash.ledger) == ["guarded"], (
        "the journal must replay the charge, not make a second one"
    )


def test_a_parent_closed_and_killed_still_stops_its_branches(crash):
    """The close is in the finalize transaction, not follow-up after it.

    This is the scenario the whole design turns on: the process that
    finalized the parent dies with no chance to do anything else at all. If
    branch cancellation were follow-up work, the regions would still deploy.

    Args:
        crash: The worker runner.
    """
    assert crash("rollout").returncode == 0
    assert effects(crash.ledger) == [], "regions soak for an hour before deploying"

    assert_killed(crash("cascade", "after_finalize"))

    statuses = sorted(runs(crash.db).values())
    assert statuses == ["CANCELLED", "CANCELLING", "CANCELLING"], (
        f"branches must be marked on disk by the finalize itself, got {statuses}"
    )

    time.sleep(LEASE_LAPSE)
    assert crash("recover").returncode == 0
    assert effects(crash.ledger) == [], "a cancelled rollout must never deploy"
    assert sorted(runs(crash.db).values()) == ["CANCELLED"] * 3


def test_a_shipment_acked_then_crashed_lands_exactly_once(crash):
    """The correlated-delivery acceptance, with a real kill in the window.

    The shipment webhook arrives before the order workflow exists and the
    process is SIGKILLed immediately after acknowledging it. The provider
    then redelivers twice. The order workflow starts later. Exactly one
    signal must reach it -- the ledger records the handler running, and the
    run's inbox holds exactly one row for the channel, read straight from
    the database.

    Args:
        crash: The subprocess runner.
    """
    first = crash("ingest_shipment", "after_ack")
    assert first.returncode == -9, (
        f"expected SIGKILL, got {first.returncode}: {first.stderr.decode()[-800:]}"
    )
    assert effects(crash.ledger) == ["acked"], "the ack must be durable pre-crash"

    redelivered = crash("redeliver")
    assert redelivered.returncode == 0, redelivered.stderr.decode()[-800:]
    started = crash("start_order")
    assert started.returncode == 0, started.stderr.decode()[-800:]

    ledger = effects(crash.ledger)
    assert ledger.count("shipped-handled") == 1, ledger
    assert ledger.count("redelivered") == 2, ledger

    import sqlite3

    connection = sqlite3.connect(crash.db)
    try:
        (inbox_rows,) = connection.execute(
            "SELECT COUNT(*) FROM workflow_inbox WHERE wait_key = 'sig:shipped'"
        ).fetchone()
        (channel_rows,) = connection.execute(
            "SELECT COUNT(*) FROM workflow_channel_inbox"
        ).fetchone()
        (delivered_rows,) = connection.execute(
            "SELECT COUNT(*) FROM workflow_channel_inbox WHERE status = 'DELIVERED'"
        ).fetchone()
    finally:
        connection.close()
    assert inbox_rows == 1, "exactly one signal reached the run"
    assert channel_rows == 1, "three deliveries are one durable event"
    assert delivered_rows == 1


def test_a_run_admitted_then_killed_is_the_same_run_when_redelivered(crash):
    """Row: killed after admission, before the ack.

    The provider never heard back, so it retries; the request key must return
    the run the dead process admitted rather than a second one.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("admit_only", "after_admit"))
    assert effects(crash.ledger) == ["admitted"]
    assert len(runs(crash.db)) == 1, "the admission was durable before the kill"

    assert_finished(crash("readmit"))
    assert effects(crash.ledger) == ["admitted", "deduplicated", "guarded"]
    assert list(runs(crash.db).values()) == ["COMPLETED"], "still exactly one run"


def test_a_successor_scheduled_by_a_commit_outlives_its_committer(crash):
    """Row: killed after commit, before any follow-up.

    The process dies inside the post-commit notification of the step that
    scheduled the successor -- no wakeup, no next claim, nothing. The
    successor must already be on disk.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("chain", "after_commit:crash.chain:attempt_succeeded"))
    assert effects(crash.ledger) == ["first"]

    time.sleep(LEASE_LAPSE)
    assert_finished(crash("recover"))
    assert effects(crash.ledger) == ["first", "second"], (
        "the successor was part of the commit; the first step never re-runs"
    )
    assert list(runs(crash.db).values()) == ["COMPLETED"]


def test_a_child_finished_and_killed_still_reaches_its_parent(crash):
    """Row: killed between a child's terminal commit and anything else.

    The fast branch completes and the process dies in that commit's
    notification. If the parent arrival were follow-up work, the join would
    wait forever once the slow branch finished; it must already be counted.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("burst", "after_commit:crash.quick:run_completed"))
    assert effects(crash.ledger) == ["quick:a"]
    # The sibling may be mid-attempt (RUNNING) or already parked on its timer
    # (WAITING) at the instant of the kill; either is fine. What must hold is
    # that exactly the killed child finished and nothing else is terminal.
    statuses = sorted(runs(crash.db).values())
    assert statuses.count("COMPLETED") == 1, statuses
    assert all(status in ("RUNNING", "WAITING") for status in statuses[1:]), statuses

    assert_finished(crash("recover", CRASH_CLOCK_OFFSET="3700"))
    assert effects(crash.ledger) == ["quick:a", "deploy:eu", "burst-report"], (
        "the join heard the dead process's child exactly once"
    )
    assert sorted(runs(crash.db).values()) == ["COMPLETED"] * 3


def test_a_worker_dying_with_two_claims_has_each_recovered(crash):
    """Row: worker dies holding N claims.

    Both attempts are in flight when the process dies. Each lease lapses and
    each step is recovered on its own; neither is lost and neither is skipped.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("slow_pair", "both_claimed"))
    assert sorted(effects(crash.ledger)) == ["slow:1", "slow:2"]
    claimed = query(
        crash.db, "SELECT status FROM workflow_steps WHERE status = 'CLAIMED'"
    )
    assert len(claimed) == 2, "both claims were on disk when the worker died"

    time.sleep(LEASE_LAPSE)
    assert_finished(crash("recover"))
    assert sorted(effects(crash.ledger)) == ["slow:1", "slow:1", "slow:2", "slow:2"], (
        "each unguarded attempt re-executes once, independently"
    )
    assert sorted(runs(crash.db).values()) == ["COMPLETED", "COMPLETED"]
    assert history_count(crash.db, "step_recovered") == 2


def test_a_killed_recovery_sweep_is_redone_not_doubled(crash):
    """Row: killed during the recovery sweep.

    The sweep's transaction commits and the process dies before the kernel
    does anything with the result. The next process's sweep finds nothing
    left to recover and the step runs exactly once.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("unguarded", "after_claim"))
    time.sleep(LEASE_LAPSE)

    assert_killed(crash("recover", "after_recover_orphans"))
    assert effects(crash.ledger) == [], "recovered, not yet run"
    assert history_count(crash.db, "step_recovered") == 1

    assert_finished(crash("recover"))
    assert effects(crash.ledger) == ["unguarded"]
    assert history_count(crash.db, "step_recovered") == 1, "the sweep is idempotent"
    assert list(runs(crash.db).values()) == ["COMPLETED"]


def test_runs_pinned_to_a_dead_release_wait_for_it(crash):
    """Row: the last worker of release R dies holding claims.

    A v2 worker recovers the lapsed lease but must not claim the step; the
    run waits, visibly pinned, until a v1 worker returns and finishes it.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("pinned", "mid_attempt", REFLEX_RELEASE_ID="v1"))
    assert effects(crash.ledger) == ["sleepy"]
    time.sleep(LEASE_LAPSE)

    assert_finished(crash("recover", REFLEX_RELEASE_ID="v2"))
    assert effects(crash.ledger) == ["sleepy"], "v2 must not run v1's step"
    assert history_count(crash.db, "step_recovered") == 1, "v2 did recover it"
    ((status, release),) = query(
        crash.db, "SELECT status, release_id FROM workflow_runs"
    )
    assert (status, release) == ("RUNNING", "v1"), "waiting, and saying for whom"

    assert_finished(crash("recover", REFLEX_RELEASE_ID="v1"))
    assert effects(crash.ledger) == ["sleepy", "sleepy"]
    assert list(runs(crash.db).values()) == ["COMPLETED"]


def test_an_hour_of_downtime_fires_the_timer_on_restart(crash):
    """Row: everything down for an hour.

    The run is asleep on a one-hour timer when the process dies. A restart
    an hour later fires it; a restart a moment later does not.

    Args:
        crash: The worker runner.
    """
    assert_killed(crash("sleeper", "asleep"))
    assert effects(crash.ledger) == []

    assert_finished(crash("recover"))
    assert effects(crash.ledger) == [], "not due yet"

    assert_finished(crash("recover", CRASH_CLOCK_OFFSET="3700"))
    assert effects(crash.ledger) == ["deploy:us-west"]
    assert list(runs(crash.db).values()) == ["COMPLETED"]
