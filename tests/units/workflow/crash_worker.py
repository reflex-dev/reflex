"""A worker that dies where it is told to, for the crash-boundary tests.

Run as a subprocess so the death is real: SIGKILL to a separate process, no
unwinding, no atexit, no flush. Simulating a crash in-process is a fair test
of the store's logic and no test at all of what actually reaches the disk, so
the two together are what the contract's "kill any process at any boundary"
claim rests on.

Usage: ``crash_worker.py <db> <ledger> <phase> <crash-point>``.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from reflex_base.workflow import Retry, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import HistoryEventType, RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import SqliteRunStore

LEDGER = Path(os.environ["CRASH_LEDGER"])
CRASH_AT = os.environ["CRASH_AT"]


def record(name: str) -> None:
    """Note that a side effect really happened, durably.

    Written and fsynced before any crash can follow it: a ledger entry lost
    to the page cache would make a repeated effect look like an exactly-once
    one, which is the direction of error that matters here.

    Args:
        name: The effect that ran.
    """
    with LEDGER.open("a") as handle:
        handle.write(f"{name}\n")
        handle.flush()
        os.fsync(handle.fileno())


def die_at(point: str) -> None:
    """End this process immediately if this is the chosen boundary.

    Args:
        point: The boundary being passed.
    """
    if point == CRASH_AT:
        os.kill(os.getpid(), signal.SIGKILL)


class Charge(rx.State):
    """One step that moves money, with and without a substep journal."""

    __workflow__ = WorkflowConfig(id="crash.charge")
    charged: str = ""

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="non_idempotent_write",
        retry=Retry(max_attempts=1),
    )
    async def unguarded(self):
        """Charge without guarding the call.

        Returns:
            Completion.
        """
        die_at("after_claim")
        record("unguarded")
        die_at("after_effect")
        self.charged = "unguarded"
        return rx.complete(result={"ok": True})

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="idempotent_write",
        retry=Retry(max_attempts=1),
    )
    async def guarded(self):
        """Charge inside a substep, so the journal can replay it.

        Returns:
            Completion.
        """

        def charge_once() -> dict:
            """Make the charge.

            Returns:
                The charge.
            """
            record("guarded")
            return {"charge_id": "ch_1"}

        charge = await rx.step("charge", charge_once)
        die_at("after_step_record")
        self.charged = charge["charge_id"]
        return rx.complete(result=charge)


class Region(rx.State):
    """A branch that acts only after a delay."""

    __workflow__ = WorkflowConfig(id="crash.region")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self, region: str):
        """Soak, then deploy.

        Args:
            region: The region to deploy.

        Returns:
            A deferral.
        """
        return rx.after("1h", Region.deploy(region))

    @rx.event(durable=True, effect="non_idempotent_write")
    def deploy(self, region: str):
        """Deploy the region.

        Args:
            region: The region to deploy.

        Returns:
            Completion.
        """
        record(f"deploy:{region}")
        return rx.complete(result={"region": region})


class Rollout(rx.State):
    """A parent that fans out to two regions."""

    __workflow__ = WorkflowConfig(id="crash.rollout")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self):
        """Fan out.

        Returns:
            The fan-out.
        """
        return rx.parallel(
            Region.start("us-east"), Region.start("eu"), then=Rollout.report
        )

    @rx.event(durable=True, effect="none")
    def report(self, results: list):
        """Report the rollout.

        Args:
            results: One entry per region.

        Returns:
            Completion.
        """
        record("report")
        return rx.complete(result={"regions": len(results)})


def _write_run_id(run_id: str) -> None:
    """Hand the parent run's identity to the next phase.

    Args:
        run_id: The run to record.
    """
    Path(sys.argv[2] + ".runid").write_text(run_id)


def _read_run_id() -> str:
    """Read the parent run's identity left by an earlier phase.

    Returns:
        The run id.
    """
    return Path(sys.argv[2] + ".runid").read_text().strip()


async def main() -> None:
    """Drive one phase of a crash scenario against a shared SQLite store."""
    db, _, phase = sys.argv[1], sys.argv[2], sys.argv[3]
    store = SqliteRunStore(Path(db))
    runtime = WorkflowRuntime(store, lease_duration=1.0)
    for workflow_cls in (Charge, Region, Rollout):
        runtime.register(workflow_cls)
    await runtime.startup(start_worker=False)
    kernel = runtime.kernel

    if phase in ("unguarded", "guarded"):
        await kernel.start(getattr(Charge, phase)())
        await kernel.recover()
        await kernel.run_until_idle()
    elif phase == "rollout":
        started = await kernel.start(Rollout.begin())
        await kernel.run_until_idle()
        die_at("after_fanout")
        assert started.run_id is not None
        _write_run_id(started.run_id)
    elif phase == "cascade":
        run_id = _read_run_id()
        # Straight at the store, so the kill lands between the finalize
        # transaction and literally anything else this process might do.
        assert await store.request_cancel(run_id, await _now(store))
        assert await store.finalize_run(
            run_id,
            status=RunStatus.CANCELLED,
            error=None,
            event=HistoryEventType.RUN_CANCELLED,
            now=await _now(store),
        )
        die_at("after_finalize")
    else:
        await kernel.recover()
        await kernel.run_until_idle()
    store.close()


async def _now(store: SqliteRunStore) -> float:
    """Read the store's clock, falling back to this process's.

    Args:
        store: The store.

    Returns:
        Epoch seconds.
    """
    import time

    return await store.epoch_time() or time.time()


asyncio.run(main())
