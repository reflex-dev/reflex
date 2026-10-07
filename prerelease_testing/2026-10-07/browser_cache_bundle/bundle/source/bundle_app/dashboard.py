"""Small stateful dashboard."""

import reflex as rx
from .common import shell


class DashboardState(rx.State):
    """Small realistic dashboard state independent of heavy-route state."""

    count: int = 0
    tasks: list[str] = ["Review shipment", "Approve invoice", "Reconcile inventory"]

    @rx.event
    def complete_task(self):
        """Record completion of one task."""
        self.count += 1


def dashboard() -> rx.Component:
    """Build task summaries and a small backend event.

    Returns:
        Dashboard route content.
    """
    return shell(
        "Operations dashboard",
        rx.text("Completed tasks: ", DashboardState.count, id="task-count"),
        rx.button(
            "Complete task", on_click=DashboardState.complete_task, id="complete-task"
        ),
        rx.vstack(rx.foreach(DashboardState.tasks, lambda task: rx.text(task))),
        rx.link("Inspect revenue chart", href="/reports", id="open-reports"),
    )
