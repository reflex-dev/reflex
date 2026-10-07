"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

import reflex_enterprise as rxe

from .basic import basic_page
from .common import DemoState, demo
from .foreach import foreach_page
from .kanban import kanban_page

__all__ = [
    "basic_page",
    "foreach_page",
    "kanban_page",
]


@demo(
    route="/",
    title="Drag and Drop Demo",
    description="A collection of examples using React-Dnd in Reflex.",
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
