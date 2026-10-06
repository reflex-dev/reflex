"""Pill demo page."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


@demo(
    route="/pill",
    title="Pill",
    description="A pill is a small, rounded component that can be used to represent a single value or a small set of values.",
)
def pill_page():
    """Pill demo page."""
    return rx.vstack(
        rx.hstack(
            rxe.mantine.pill("Default"),
            rxe.mantine.pill("Default", color="red"),
            rxe.mantine.pill(
                "Default", with_remove_button=True, on_remove=rx.toast("Removed")
            ),
            spacing="2",
        ),
        rxe.mantine.pill.group(
            rxe.mantine.pill("Default", size="xs"),
            rxe.mantine.pill("Default", size="sm"),
            rxe.mantine.pill("Default", size="md"),
            rxe.mantine.pill("Default", size="lg"),
        ),
        spacing="4",
    )
