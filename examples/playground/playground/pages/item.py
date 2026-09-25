"""The item page, a dynamic route."""

import reflex as rx

from playground.layout import layout


def item() -> rx.Component:
    """Render the page of one item.

    Returns:
        The item id taken from the URL.
    """
    return layout(
        rx.vstack(
            rx.heading("Item"),
            # Dynamic route arguments are vars of the root state.
            rx.text("item_id: ", rx.code(rx.State.item_id, id="item-id")),  # pyright: ignore[reportAttributeAccessIssue]
        )
    )
