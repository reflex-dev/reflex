"""Backend events for the realistic memoized dashboard."""

import reflex as rx

from .settings import STATE_DEFAULT, STEP


class State(rx.State):
    """Track a total and customer name across browser interactions."""

    total: int = 0
    customer: str = STATE_DEFAULT
    mounts: list[str] = []

    @rx.event
    def record_mount(self, label: str):
        """Record which visually identical component actually mounted.

        Args:
            label: Expected side and application revision.
        """
        if label not in self.mounts:
            self.mounts.append(label)

    @rx.event
    def increase(self):
        """Apply the currently imported increment rule."""
        self.total += STEP

    @rx.event
    def rename(self, value: str):
        """Store the customer name.

        Args:
            value: The edited customer name.
        """
        self.customer = value
