"""Exercise expiry and persistence through ordinary browser events."""

import asyncio
import json
import os
import time
from pathlib import Path

import reflex as rx

assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in rx.__file__, rx.__file__


class Stockroom(rx.State):
    """Root application state."""

    root_count: int = 0
    receipt: str = ""
    job_status: str = "idle"

    @rx.event
    def increment_root(self):
        """Record one root-state action."""
        self.root_count += 1

    @rx.event(background=True)
    async def external_job(self):
        """Release state while simulated external work outlasts its idle TTL."""
        async with self:
            self.job_status = "running"
        await asyncio.sleep(float(os.environ["QA_JOB_DELAY"]))
        async with self:
            self.root_count += 10
            self.job_status = "completed"

    @rx.event
    async def hold(self):
        """Hold the ordinary event lock longer than the configured TTL."""
        self.job_status = "holding"
        await asyncio.sleep(float(os.environ["QA_JOB_DELAY"]))
        self.root_count += 10
        self.job_status = "held-completed"

    @rx.event
    async def inspect(self):
        """Show the server's values without changing the counters."""
        child = await self.get_state(Shelf)
        first = await self.get_state(counter_a.State)
        second = await self.get_state(counter_b.State)
        self.receipt = json.dumps(
            {
                "root": self.root_count,
                "child": child.child_count,
                "a": first.count,
                "b": second.count,
            },
            sort_keys=True,
        )


class Shelf(Stockroom):
    """Nested state with an independent count."""

    child_count: int = 0

    @rx.event
    def increment_child(self):
        """Record one substate action."""
        self.child_count += 1


class Counter(rx.ComponentState):
    """Independent component-local count."""

    count: int = 0

    @rx.event
    def increment(self):
        """Record one component action."""
        self.count += 1

    @classmethod
    def get_component(cls, label: str, **props):
        """Render a counter instance.

        Args:
            label: Stable DOM label for this instance.
            **props: Container properties.

        Returns:
            Counter text and button.
        """
        return rx.vstack(
            rx.text(cls.count, id=f"count-{label}"),
            rx.button(f"Add {label}", id=f"add-{label}", on_click=cls.increment),
            **props,
        )


counter_a = Counter.create(label="a")
counter_b = Counter.create(label="b")


def index():
    """Render the root, substate and component counters.

    Returns:
        A compact session dashboard.
    """
    return rx.vstack(
        rx.heading("Stockroom session expiry"),
        rx.text(Stockroom.root_count, id="count-root"),
        rx.button("Add root", id="add-root", on_click=Stockroom.increment_root),
        rx.text(Shelf.child_count, id="count-child"),
        rx.button("Add child", id="add-child", on_click=Shelf.increment_child),
        counter_a,
        counter_b,
        rx.button("Inspect saved counts", id="inspect", on_click=Stockroom.inspect),
        rx.text(Stockroom.receipt, id="receipt"),
        rx.text(Stockroom.job_status, id="job-status"),
        rx.button("External job", id="external-job", on_click=Stockroom.external_job),
        rx.button("Hold then finish", id="hold", on_click=Stockroom.hold),
        padding="2em",
    )


async def observe_manager(app):
    """Sample manager bookkeeping without loading, touching or changing states.

    Args:
        app: Running Reflex app supplied by the public lifespan API.
    """
    manager = app.state_manager
    path = Path(os.environ["QA_METRICS"])
    previous = None
    last_written = 0.0
    with path.open("a") as stream:
        while True:
            locks = manager._states_locks
            row = {
                "pid": os.getpid(),
                "manager": type(manager).__name__,
                "expiration_seconds": manager.token_expiration,
                "debounce_seconds": getattr(manager, "_write_debounce_seconds", None),
                "states": len(manager.states),
                "locks": len(locks),
                "locked": sum(lock.locked() for lock in locks.values()),
                "pending_writes": len(getattr(manager, "_write_queue", {})),
                "deadlines": len(getattr(manager, "_token_expires_at", {})),
                "touched": len(getattr(manager, "_token_last_touched", {})),
            }
            now = time.time()
            if row != previous or now - last_written >= 1:
                stream.write(json.dumps({"time": now, **row}) + "\n")
                stream.flush()
                previous = row
                last_written = now
            await asyncio.sleep(0.2)


app = rx.App()
app.add_page(index)
app.register_lifespan_task(observe_manager)
