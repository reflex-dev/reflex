"""Test (c): dynamic components + bundle_library on 0.9.9a1 RegistrationContext."""

import reflex as rx
from reflex.components.dynamic import bundle_library

# User-level bundle_library at module import time (the pattern third-party libs use).
bundle_library("lucide-react")


class DynState(rx.State):
    """State serving dynamic components."""

    label: str = "start"

    # Plain Component state var (radix button -> needs bundled @radix-ui/themes).
    button: rx.Component = rx.button("dyn-button-initial", id="dyn-button")

    @rx.event
    def got_clicked(self):
        """Replace the dynamic button when clicked."""
        self.button = rx.button("dyn-button-clicked", id="dyn-button")

    @rx.event
    def relabel(self):
        """Change the label shown inside the computed dynamic component."""
        self.label = "clicked"

    @rx.var
    def dyn_block(self) -> rx.Component:
        """Computed dynamic component using a lucide icon + state interpolation.

        Returns:
            The dynamic component.
        """
        return rx.vstack(
            rx.icon("apple", id="dyn-icon"),
            rx.text(f"label: {self.label}", id="dyn-label"),
            rx.button(
                "relabel-inside-dyn",
                id="dyn-relabel",
                on_click=DynState.relabel,
            ),
        )


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("DYNAPP", id="marker"),
        rx.icon("banana", id="static-icon"),
        DynState.button,
        rx.button(
            "swap-dyn-button", id="swap-btn", on_click=DynState.got_clicked
        ),
        DynState.dyn_block,
        spacing="4",
    )


app = rx.App()
app.add_page(index)
