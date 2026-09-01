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
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from reflex_base.workflow import Retry, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.kernel import WorkflowObserver
from reflex.workflow.records import HistoryEventType, RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import SqliteRunStore

LEDGER = Path(os.environ["CRASH_LEDGER"])
CRASH_AT = os.environ["CRASH_AT"]
# "Everything down for an hour" is a restart with the clock moved on, so the
# recovering process may be told how far.
CLOCK_OFFSET = float(os.environ.get("CRASH_CLOCK_OFFSET", "0"))


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


class KillingObserver(WorkflowObserver):
    """Dies inside the post-commit notification.

    The observer runs after a commit's transaction and before any of the
    worker's follow-ups -- wakeups, loser cancellation, the next claim -- so
    ``after_commit:<workflow>:<event>`` is the row "killed after commit (any
    transition)" made real.
    """

    def on_event(
        self,
        event_type: HistoryEventType,
        run_id: str,
        workflow_id: str,
        data: dict[str, Any],
    ) -> None:
        """Die if this commit is the chosen boundary.

        Args:
            event_type: What was just committed.
            run_id: The run it happened to.
            workflow_id: That run's workflow identity.
            data: The event payload.
        """
        die_at(f"after_commit:{workflow_id}:{event_type.value}")


class KillingStore(SqliteRunStore):
    """A store that can die right after its recovery sweep commits."""

    async def recover_orphans(self, now: float, max_recoveries: int):
        """Sweep, then die if the sweep is the chosen boundary.

        Args:
            now: The current time.
            max_recoveries: The recovery budget per step.

        Returns:
            What the sweep returned.
        """
        result = await super().recover_orphans(now, max_recoveries)
        die_at("after_recover_orphans")
        return result


IN_FLIGHT: set[int] = set()


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


class Order(rx.State):
    """A run that waits for a correlated shipment event."""

    __workflow__ = WorkflowConfig(id="crash.order")

    shipped = rx.Signal()

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self):
        """Wait for the shipment.

        Returns:
            The wait.
        """
        return rx.wait_for(Order.shipped, then=Order.close, timeout=rx.never)

    @rx.event(durable=True, effect="none", retry=Retry(max_attempts=1))
    def close(self, shipment):
        """Handle the shipment; the ledger is the exactly-once evidence.

        Args:
            shipment: The delivered payload.

        Returns:
            Completion.
        """
        record("shipped-handled")
        return rx.complete(result=shipment)


class Chain(rx.State):
    """Two steps; the first's commit schedules the second."""

    __workflow__ = WorkflowConfig(id="crash.chain")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def first(self):
        """Run, and schedule the successor.

        Returns:
            The deferral.
        """
        record("first")
        return rx.after("1s", Chain.second())

    @rx.event(durable=True, effect="none")
    def second(self):
        """Run the successor.

        Returns:
            Completion.
        """
        record("second")
        return rx.complete(result={"ok": True})


class Quick(rx.State):
    """A branch that finishes at once."""

    __workflow__ = WorkflowConfig(id="crash.quick")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def go(self, name: str):
        """Finish.

        Args:
            name: The branch's name.

        Returns:
            Completion.
        """
        record(f"quick:{name}")
        return rx.complete(result=name)


class Burst(rx.State):
    """A parent with one fast branch and one that sleeps an hour."""

    __workflow__ = WorkflowConfig(id="crash.burst")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self):
        """Fan out.

        Returns:
            The fan-out.
        """
        return rx.parallel(Quick.go("a"), Region.start("eu"), then=Burst.report)

    @rx.event(durable=True, effect="none")
    def report(self, results: list):
        """Report once both branches arrived.

        Args:
            results: One entry per branch.

        Returns:
            Completion.
        """
        record("burst-report")
        return rx.complete(result={"branches": len(results)})


class Slow(rx.State):
    """An attempt that holds its claim long enough for a peer to join it."""

    __workflow__ = WorkflowConfig(id="crash.slow")

    @rx.event(
        durable=True, trigger=manual(), effect="none", retry=Retry(max_attempts=1)
    )
    async def go(self, n: int):
        """Record, then hold the claim; die once two are held.

        Args:
            n: Which run this is.

        Returns:
            Completion.
        """
        record(f"slow:{n}")
        IN_FLIGHT.add(n)
        if len(IN_FLIGHT) == 2:
            die_at("both_claimed")
        await asyncio.sleep(0.5)
        return rx.complete(result=n)


class Sleepy(rx.State):
    """One step whose attempt can die mid-way."""

    __workflow__ = WorkflowConfig(id="crash.sleepy")

    @rx.event(
        durable=True, trigger=manual(), effect="none", retry=Retry(max_attempts=1)
    )
    def go(self):
        """Record, maybe die, finish.

        Returns:
            Completion.
        """
        record("sleepy")
        die_at("mid_attempt")
        return rx.complete(result={"ok": True})


async def main() -> None:
    """Drive one phase of a crash scenario against a shared SQLite store."""
    db, _, phase = sys.argv[1], sys.argv[2], sys.argv[3]
    store = KillingStore(Path(db))
    runtime = WorkflowRuntime(
        store,
        lease_duration=1.0,
        clock=lambda: time.time() + CLOCK_OFFSET,
        observer=KillingObserver(),
    )
    for workflow_cls in (
        Charge,
        Region,
        Rollout,
        Order,
        Chain,
        Quick,
        Burst,
        Slow,
        Sleepy,
    ):
        runtime.register(workflow_cls)
    await runtime.startup(start_worker=False)
    kernel = runtime.kernel

    if phase == "admit_only":
        # Admitted, durable, and killed before anything could acknowledge it.
        started = await kernel.start(Charge.guarded(), request_key="charge_1")
        assert started.disposition == "started", started.disposition
        record("admitted")
        die_at("after_admit")
    elif phase == "readmit":
        # The provider's redelivery from a fresh process: same key, same run.
        started = await kernel.start(Charge.guarded(), request_key="charge_1")
        assert started.disposition == "deduplicated", started.disposition
        record("deduplicated")
        await kernel.run_until_idle()
    elif phase == "chain":
        await kernel.start(Chain.first())
        await kernel.run_until_idle()
    elif phase == "burst":
        await kernel.start(Burst.begin())
        await kernel.run_until_idle()
    elif phase == "slow_pair":
        await kernel.start(Slow.go(1))
        await kernel.start(Slow.go(2))
        await kernel.run_until_idle()
    elif phase == "pinned":
        await kernel.start(Sleepy.go())
        await kernel.run_until_idle()
    elif phase == "sleeper":
        await kernel.start(Region.start("us-west"))
        await kernel.run_until_idle()
        die_at("asleep")
    elif phase == "ingest_shipment":
        # The provider's first delivery: durable, acked, then the process is
        # killed with nothing else done -- the crash-after-ack window.
        disposition = await kernel.ingest_channel(
            "crash.order", "shipped", "order_1", "evt_1", {"parcel": "P-1"}
        )
        assert disposition == "parked", disposition
        record("acked")
        die_at("after_ack")
    elif phase == "redeliver":
        # The provider retries twice from a fresh process; both must collapse
        # into the durable row the crashed process left behind.
        for _ in range(2):
            disposition = await kernel.ingest_channel(
                "crash.order", "shipped", "order_1", "evt_1", {"parcel": "P-1"}
            )
            assert disposition == "duplicate", disposition
            record("redelivered")
    elif phase == "start_order":
        started = await kernel.start(Order.begin(), request_key="order_1")
        assert started.run_id is not None
        _write_run_id(started.run_id)
        await kernel.run_until_idle()
    elif phase in ("unguarded", "guarded"):
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
