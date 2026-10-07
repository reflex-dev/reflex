"""Inventory events and routes using the plugin's documented instrumentor."""

import asyncio

import reflex as rx
from reflex_otel import ReflexInstrumentor

ReflexInstrumentor().instrument()
ReflexInstrumentor().instrument()


class Inventory(rx.State):
    """Track user actions independently of telemetry delivery."""

    count: int = 0
    audited: int = 0
    jobs: int = 0
    status: str = "idle"
    note: str = ""

    @rx.event
    def add(self):
        """Add one item and enqueue its audit event.

        Returns:
            The audit event chained to this interaction.
        """
        self.count += 1
        return Inventory.audit()

    @rx.event
    def audit(self):
        """Count the chained audit event."""
        self.audited += 1

    @rx.event
    def fail(self):
        """Raise an intentional error to verify span status and recovery.

        Raises:
            ValueError: Deliberate synthetic test failure.
        """
        raise ValueError("QA deliberate inventory failure")

    @rx.event
    def set_note(self, value: str):
        """Store synthetic user input that must not be exported.

        Args:
            value: Synthetic test payload.
        """
        self.note = value

    @rx.event(background=True)
    async def replenish(self):
        """Complete three increments across asynchronous state contexts."""
        async with self:
            self.status = "running"
        for _ in range(3):
            await asyncio.sleep(0.15)
            async with self:
                self.jobs += 1
        async with self:
            self.status = "done"


def controls() -> rx.Component:
    """Render state and public user actions on either route.

    Returns:
        Shared inventory controls.
    """
    return rx.vstack(
        rx.text(Inventory.count, id="count"),
        rx.text(Inventory.audited, id="audited"),
        rx.text(Inventory.jobs, id="jobs"),
        rx.text(Inventory.status, id="status"),
        rx.input(value=Inventory.note, on_change=Inventory.set_note, id="note"),
        rx.text(Inventory.note, id="note-value"),
        rx.button("Add inventory", id="add", on_click=Inventory.add),
        rx.button("Replenish", id="job", on_click=Inventory.replenish),
        rx.button("Test failure", id="fail", on_click=Inventory.fail),
    )


def index() -> rx.Component:
    """Render the initial inventory route.

    Returns:
        Inventory dashboard.
    """
    return rx.vstack(
        rx.heading("Inventory telemetry", id="page-home"),
        controls(),
        rx.link("Audit route", href="/audit", id="route-audit"),
    )


def audit_page() -> rx.Component:
    """Render a routed view sharing the same inventory state.

    Returns:
        Audit dashboard.
    """
    return rx.vstack(
        rx.heading("Audit", id="page-audit"),
        controls(),
        rx.link("Inventory route", href="/", id="route-home"),
    )


def handle_error(exception: Exception):
    """Show a controlled toast for the synthetic handler failure.

    Args:
        exception: Exception captured by the framework.

    Returns:
        A toast event that leaves the inventory usable.
    """
    return rx.toast.error(str(exception))


app = rx.App(backend_exception_handler=handle_error)
app.add_page(index)
app.add_page(audit_page, route="/audit")
