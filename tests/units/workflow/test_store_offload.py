"""Tests that SQLite store calls do not stall the event loop.

The store's calls run on the loop that also serves the app's HTTP and
websocket traffic. A slow or contended SQLite call executed inline therefore
freezes every request in the process for its duration; moved to a worker
thread, the loop keeps serving while the disk does its work.
"""

import asyncio
import time

from reflex.workflow.records import (
    HistoryEventType,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
)
from reflex.workflow.store import SqliteRunStore


def _seed(now: float) -> tuple[RunRecord, StepRecord]:
    """Build one admissible run.

    Args:
        now: Current time in epoch seconds.

    Returns:
        The run and its root slot.
    """
    return (
        RunRecord(
            run_id="r1",
            workflow_id="offload.flow",
            definition_digest="d",
            status=RunStatus.PENDING,
            state={},
            state_version=0,
            next_ordinal=1,
            created_at=now,
            updated_at=now,
        ),
        StepRecord(
            run_id="r1",
            ordinal=0,
            handler_id="go",
            status=StepStatus.READY,
            args={},
            origin="root",
            created_at=now,
            updated_at=now,
        ),
    )


async def test_a_slow_sqlite_call_does_not_freeze_the_loop(tmp_path):
    """The loop keeps ticking while a store call sits on slow storage.

    The database is made artificially slow by wrapping the connection's
    execute in a quarter-second stall. A heartbeat task then counts loop
    iterations during one store call: executed inline the heartbeat cannot
    tick at all, offloaded it keeps beating.
    """
    store = SqliteRunStore(tmp_path / "slow.db")
    now = time.time()
    run, root = _seed(now)
    await store.admit(run, root, ((HistoryEventType.RUN_ADMITTED, {}),))

    real_db = store._db

    class SlowConnection:
        """Delegate to the real connection, stalling every query."""

        def execute(self, *args, **kwargs):
            """Stall, then run the real query.

            Args:
                args: Positional query arguments.
                kwargs: Keyword query arguments.

            Returns:
                The real cursor.
            """
            time.sleep(0.25)
            return real_db.execute(*args, **kwargs)

        def __getattr__(self, name):
            """Delegate everything else.

            Args:
                name: The attribute being read.

            Returns:
                The real connection's attribute.
            """
            return getattr(real_db, name)

    store._db = SlowConnection()  # pyright: ignore[reportAttributeAccessIssue]

    beats = 0
    ticking = True

    async def heartbeat():
        """Count loop iterations while the store call runs."""
        nonlocal beats
        while ticking:
            beats += 1
            await asyncio.sleep(0.01)

    ticker = asyncio.ensure_future(heartbeat())
    try:
        await asyncio.sleep(0.03)
        assert await store.get_run("r1") is not None
    finally:
        ticking = False
        await ticker
        store._db = real_db
        store.close()

    # A quarter-second stall should allow ~25 beats; even a loaded CI box
    # manages a handful. Inline execution allows exactly the few from before
    # the call started.
    assert beats >= 10, f"loop only ticked {beats} times during the store call"
