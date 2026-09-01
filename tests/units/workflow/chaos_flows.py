"""Workflows and a durable effects ledger for the chaos soak.

Shared by the driver (the test) and the worker subprocesses, so both sides
agree on what a run is and where effects are recorded. Every side effect is
a row in a separate SQLite ledger committed before the handler continues, so
a kill can never lose the evidence of an effect that really happened.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path

from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.context import current_run
from reflex.workflow.store import RunStore, SqliteRunStore

LEDGER_ENV = "CHAOS_LEDGER"


def _ledger() -> sqlite3.Connection:
    """Open the ledger, creating its one table.

    Returns:
        The connection.
    """
    connection = sqlite3.connect(os.environ[LEDGER_ENV], timeout=30)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS effects (name TEXT NOT NULL, key TEXT UNIQUE)"
    )
    return connection


def record(name: str) -> None:
    """Durably note that a side effect happened.

    Args:
        name: The effect.
    """
    connection = _ledger()
    try:
        with connection:
            connection.execute("INSERT INTO effects (name) VALUES (?)", (name,))
    finally:
        connection.close()


def record_once(name: str, key: str) -> None:
    """Record an effect the way an idempotent provider would.

    The provider is the one place a repeated call can be collapsed: it keeps
    the idempotency key it was handed and ignores a second call carrying the
    same one. This is the defense the contract prescribes for the window
    between a provider call and its ``rx.step`` record (§2, §8).

    Args:
        name: The effect.
        key: The run's idempotency key for this step.
    """
    connection = _ledger()
    try:
        with connection:
            connection.execute(
                "INSERT OR IGNORE INTO effects (name, key) VALUES (?, ?)", (name, key)
            )
    finally:
        connection.close()


def first_time(name: str) -> bool:
    """Note an occurrence and say whether it was the first.

    A durable once-flag: the way a handler can fail exactly its first business
    attempt and succeed on the retry, whichever process runs which.

    Args:
        name: The occurrence.

    Returns:
        True the first time this name is recorded.
    """
    connection = _ledger()
    try:
        with connection:
            ((seen,),) = connection.execute(
                "SELECT COUNT(*) FROM effects WHERE name = ?", (name,)
            ).fetchall()
            connection.execute("INSERT INTO effects (name) VALUES (?)", (name,))
        return seen == 0
    finally:
        connection.close()


def effects() -> list[str]:
    """Read every recorded effect.

    Returns:
        The effect names, in the order they were recorded.
    """
    connection = _ledger()
    try:
        return [row[0] for row in connection.execute("SELECT name FROM effects")]
    finally:
        connection.close()


def open_store(target: str, schema: str) -> RunStore:
    """Open the store the soak runs on.

    Args:
        target: A Postgres URL or a SQLite path.
        schema: The Postgres schema; ignored for SQLite.

    Returns:
        The store.
    """
    if target.startswith("postgres"):
        from reflex.workflow.postgres import PostgresRunStore

        return PostgresRunStore(target, schema=schema, min_size=0, max_size=4)
    return SqliteRunStore(Path(target))


class Payment(rx.State):
    """A guarded charge, a durable timer, then a settlement that flakes once."""

    __workflow__ = WorkflowConfig(id="chaos.payment")

    @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
    async def pay(self, order: str):
        """Charge inside a substep, then wait before settling.

        Args:
            order: The order.

        Returns:
            The deferral.
        """
        context = current_run()
        assert context is not None
        key = context.idempotency_key()

        def charge_once() -> dict:
            """Call the provider: every call is counted, the provider dedupes.

            Returns:
                The charge.
            """
            record(f"charge-attempt:{order}")
            record_once(f"charge:{order}", key)
            return {"charge_id": f"ch_{order}"}

        charge = await rx.step("charge", charge_once)
        return rx.after("1s", Payment.settle(charge["charge_id"]))

    @rx.event(
        durable=True,
        effect="idempotent_write",
        retry=Retry(max_attempts=3, initial_delay=0.2),
    )
    async def settle(self, charge_id: str):
        """Hold the claim a while, fail the first business attempt, succeed after.

        Args:
            charge_id: The charge to settle.

        Returns:
            Completion.

        Raises:
            TransientWorkflowError: On the first attempt, always.
        """
        # Long enough that a random kill lands while this claim is held.
        await asyncio.sleep(0.3)
        if first_time(f"settle-flake:{charge_id}"):
            msg = "settlement provider blipped"
            raise TransientWorkflowError(msg)
        record(f"settle:{charge_id}")
        return rx.complete(result={"charge_id": charge_id})


class Shipment(rx.State):
    """A run that waits for a correlated signal the driver sends."""

    __workflow__ = WorkflowConfig(id="chaos.shipment")
    shipped = rx.Signal()

    @rx.event(durable=True, trigger=manual(), effect="none")
    def ship(self, order: str):
        """Wait for the shipment.

        Args:
            order: The order.

        Returns:
            The wait.
        """
        return rx.wait_for(Shipment.shipped, then=Shipment.close, timeout=rx.never)

    @rx.event(durable=True, effect="idempotent_write")
    def close(self, payload):
        """Record the shipment once.

        Args:
            payload: The delivered payload.

        Returns:
            Completion.
        """
        record(f"close:{payload['order']}")
        return rx.complete(result=payload)


class Region(rx.State):
    """A fan-out branch with one guarded effect."""

    __workflow__ = WorkflowConfig(id="chaos.region")

    @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
    async def go(self, name: str, rollout: str):
        """Deploy inside a substep.

        Args:
            name: The region.
            rollout: The parent rollout.

        Returns:
            Completion.
        """
        context = current_run()
        assert context is not None
        key = context.idempotency_key()

        def deploy() -> dict:
            """Deploy through an idempotent provider.

            Returns:
                The outcome.
            """
            record(f"region-attempt:{rollout}:{name}")
            record_once(f"region:{rollout}:{name}", key)
            return {"deployed": name}

        await asyncio.sleep(0.2)
        await rx.step("deploy", deploy)
        return rx.complete(result=name)


class Rollout(rx.State):
    """A parent that fans out to two regions and checks their order."""

    __workflow__ = WorkflowConfig(id="chaos.rollout")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self, rollout: str):
        """Fan out.

        Args:
            rollout: This rollout's name.

        Returns:
            The fan-out.
        """
        return rx.parallel(
            Region.go("a", rollout), Region.go("b", rollout), then=Rollout.report
        )

    @rx.event(durable=True, effect="none")
    def report(self, results: list):
        """Fail if the join heard the branches out of declaration order.

        Args:
            results: One entry per branch.

        Returns:
            Completion, or failure naming the order.
        """
        # A join delivers one arrival record per branch -- run id, status,
        # result, branch index -- in declaration order, whatever order they
        # finished in.
        outcome = [(entry["status"], entry["result"]) for entry in results]
        if outcome != [("COMPLETED", "a"), ("COMPLETED", "b")]:
            return rx.fail(f"branches arrived as {outcome!r}")
        record("report")
        return rx.complete(result=[entry["result"] for entry in results])


WORKFLOWS = (Payment, Shipment, Region, Rollout)
