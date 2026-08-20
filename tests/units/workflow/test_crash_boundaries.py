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

    def run(phase: str, crash_at: str = "none") -> subprocess.CompletedProcess:
        """Run one phase of the worker.

        Args:
            phase: Which scenario the worker should drive.
            crash_at: The boundary at which it should die.

        Returns:
            The finished process.
        """
        return subprocess.run(
            [sys.executable, str(WORKER), str(db), str(ledger), phase],
            env={**os.environ, "CRASH_LEDGER": str(ledger), "CRASH_AT": crash_at},
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
