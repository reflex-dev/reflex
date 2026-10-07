"""Memo component bodies imported by the dashboard routes."""

import reflex as rx

from .settings import ACCENT, CAPTION, COPY, INCLUDE_MOMENT
from .state import State


@rx.memo
def metric_card(title: rx.Var[str], caption: rx.Var[str] = CAPTION) -> rx.Component:
    """Render a reusable stateful metric card.

    Args:
        title: The card title.
        caption: An optional caption, defaulting to the imported setting.

    Returns:
        The memoized card body.
    """
    return rx.box(
        rx.heading(COPY, " ", title, class_name="card-title", size="4"),
        rx.text(caption, class_name="card-caption"),
        rx.text(State.customer, class_name="card-customer"),
        rx.text(State.total, class_name="card-total"),
        rx.button("Add", on_click=State.increase, class_name="card-add"),
        *(
            [rx.moment("2026-10-07", format="YYYY-MM-DD", class_name="card-moment")]
            if INCLUDE_MOMENT
            else []
        ),
        background_color=ACCENT,
        border="1px solid #9a9a9a",
        padding="16px",
        width="300px",
        class_name="metric-card",
    )
