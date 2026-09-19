"""Anchor demo page."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


@demo(
    route="/anchor",
    title="Anchor",
    description="An anchor is a component that allows you to link to a specific page.",
)
def anchor_page():
    """Anchor demo page."""
    return rx.hstack(
        rxe.anchor(
            "Anchor",
            href="https://build.reflex.dev/",
            target="_blank",
        ),
        align="center",
        spacing="4",
    )
