"""Aspect Ratio demo page."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


@demo(
    route="/aspect-ratio",
    title="Aspect Ratio",
    description="An aspect ratio is used to maintain the aspect ratio of a component.",
)
def aspect_ratio_page():
    """Aspect ratio demo page."""
    return rx.hstack(
        rxe.aspect_ratio(
            rx.image(
                src="https://reflex.dev/logo.jpg",
            ),
            ratio=1 / 1,
        ),
        align="center",
        spacing="4",
    )
