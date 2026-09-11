"""FINDING-022 acceptance app: the body supplied by the review handoff.

Apple occurs only as a grandchild of a registered prototype and after an event in
live state; Tag has no explicit registration at all.
"""

import reflex as rx
from reflex_base.components.dynamic import bundle_library


class State(rx.State):
    """Counter with a component-valued computed var."""

    count: rx.Field[int] = rx.field(0)
    activated: rx.Field[bool] = rx.field(False)

    @rx.event
    def set_count(self, count: int):
        """Set the count."""
        self.count = count

    @rx.event
    def toggle(self):
        """Toggle the activated flag."""
        self.activated = not self.activated

    @rx.var
    def counter_ui(self) -> rx.Component:
        """The dynamic component tree."""
        if self.activated:
            return rx.hstack(
                rx.icon("apple", color="green", id="dynamic-icon"),
                rx.button("-", on_click=State.set_count(self.count - 1), id="dec"),
                rx.text(self.count, id="count"),
                rx.button("+", on_click=State.set_count(self.count + 1), id="inc"),
            )
        return rx.icon("tag", color="red", id="initial-icon")


bundle_library(rx.text())
bundle_library(rx.hstack(rx.el.div(rx.icon("apple"))))


def index() -> rx.Component:
    """Index page."""
    return rx.vstack(
        rx.icon("alert"),
        rx.button("Activate", id="activate", on_click=State.toggle),
        State.counter_ui,
        rx.text("ready", id="ready"),
    )


app = rx.App()
app.add_page(index)
