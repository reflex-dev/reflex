"""Minimal end-to-end verification app for PEP695-alias state var assignment."""

from typing import Literal

import reflex as rx

type Key = Literal["a", "b"]


class VState(rx.State):
    """State with one alias-annotated var and one plain var."""

    k: Key = "a"
    plain: str = "init"

    @rx.event
    def set_alias(self):
        """Assign the alias-annotated var (claimed to crash server-side)."""
        self.k = "b"

    @rx.event
    def set_plain_var(self):
        """Assign the plain str var (control; should work)."""
        self.plain = "changed"


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.text(VState.k, id="alias-val"),
        rx.text(VState.plain, id="plain-val"),
        rx.button("set alias", id="btn-alias", on_click=VState.set_alias),
        rx.button("set plain", id="btn-plain", on_click=VState.set_plain_var),
    )


app = rx.App()
app.add_page(index)
