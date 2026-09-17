"""Cross-module memo fixture B.

Mirrors ``module_a``'s memo names with different bodies so the two modules
produce distinct memos that share an export name.
"""

import reflex as rx


@rx.memo
def my_widget(title: rx.Var[str]) -> rx.Component:
    """Same name as ``module_a.my_widget`` but a different body.

    Args:
        title: The title to render.

    Returns:
        A heading component.
    """
    return rx.heading("module_b:", title)


@rx.memo
def my_value(x: rx.Var[int]) -> rx.Var[str]:
    """Same name as ``module_a.my_value`` but a different body.

    Args:
        x: The value to format.

    Returns:
        A prefixed string var.
    """
    return "b:" + x.to(str)
