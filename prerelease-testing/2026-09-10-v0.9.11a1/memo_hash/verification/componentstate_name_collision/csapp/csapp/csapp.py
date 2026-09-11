"""App that renders two same-named ComponentState widgets from two modules."""

import reflex as rx

from .widget_a import Counter as CounterA
from .widget_b import Counter as CounterB


def index() -> rx.Component:
    """The page.

    Returns:
        The page component.
    """
    return rx.el.div(CounterA.create(), CounterB.create())


app = rx.App()
app.add_page(index, route="/samename")
