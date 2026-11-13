"""The index page, listing the items."""

import reflex as rx

from playground.components.marker import marker
from playground.layout import layout
from playground.state import PlaygroundState


def item_link(item: rx.Var[str]) -> rx.Component:
    """Render one entry of the item list.

    Args:
        item: The name of the item.

    Returns:
        A list entry linking to the page of the item.
    """
    return rx.list_item(rx.link(item, href=f"/item/{item}"))


def index() -> rx.Component:
    """Render the index page.

    Returns:
        An introduction, the item list and the leaf hot reload marker.
    """
    return layout(
        rx.vstack(
            rx.heading("Reflex playground"),
            rx.text("A small app exercising state, events and routing."),
            rx.unordered_list(rx.foreach(PlaygroundState.items, item_link)),
            marker(),
        )
    )
