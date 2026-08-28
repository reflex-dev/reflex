"""Verifier app: user-level bundle_library + computed rx.Component var with a lucide icon."""

import reflex as rx
from reflex.components.dynamic import bundle_library

bundle_library("lucide-react")


class VState(rx.State):
    """State with a computed dynamic component."""

    label: str = "start"

    @rx.event
    def relabel(self):
        """Change the label."""
        self.label = "clicked"

    @rx.var
    def dyn_block(self) -> rx.Component:
        """Computed dynamic component containing a lucide icon.

        Returns:
            The dynamic component.
        """
        return rx.vstack(
            rx.icon("apple", id="dyn-icon"),
            rx.text(f"label: {self.label}", id="dyn-label"),
        )


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("VDYNAPP", id="marker"),
        rx.icon("banana", id="static-icon"),
        VState.dyn_block,
    )


app = rx.App()
app.add_page(index)
