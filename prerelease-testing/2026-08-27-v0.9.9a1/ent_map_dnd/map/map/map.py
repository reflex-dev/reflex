"""Leaflet Map Demos for Reflex Enterprise."""

import reflex as rx

import reflex_enterprise as rxe

from .common import DemoState, demo
from .fly_to_location import fly_to_location
from .map_controls import map_controls
from .vector_layers import vector_layers

__all__ = [
    "fly_to_location",
    "map_controls",
    "vector_layers",
]


@demo(
    route="/",
    title="Map Demos",
    description="A collection of examples showcasing Leaflet maps in Reflex Enterprise.",
)
def index():
    return rx.flex(
        rx.foreach(
            DemoState.pages,
            lambda page: rx.card(
                rx.vstack(
                    rx.link(page.title, href=page.route),
                    rx.text(page.description),
                ),
                width="300px",
            ),
        ),
        wrap="wrap",
        spacing="3",
    )


app = rxe.App()
