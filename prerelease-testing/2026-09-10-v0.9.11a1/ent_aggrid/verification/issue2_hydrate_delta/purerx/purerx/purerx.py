"""Blast radius probe: ONE state var that cannot be JSON-serialized.

No reflex-enterprise involved. Shows what happens to the rest of the hydrate delta.
"""

from typing import Any

import reflex as rx

print("VERIFY reflex from:", rx.__file__, flush=True)
assert "/envs/" in rx.__file__, rx.__file__


class Unserializable:
    """A plain object with no registered serializer."""


class PureState(rx.State):
    """One good var, one var reflex cannot serialize."""

    count: int = 0
    payload: dict[str, Any] = {"obj": Unserializable()}

    @rx.event
    def inc(self):
        """Increment the counter."""
        self.count += 1


def index() -> rx.Component:
    """The only page."""
    return rx.vstack(
        rx.heading("pure reflex blast radius"),
        rx.button(PureState.count.to_string(), on_click=PureState.inc, id="btn"),
    )


app = rx.App()
app.add_page(index)
