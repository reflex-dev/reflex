"""Cross-module memo fixture A.

Defines memos whose names also exist in ``module_b`` and ``module_c`` so the
same export name compiles in more than one module.
"""

import reflex as rx


@rx.memo
def my_widget(title: rx.Var[str]) -> rx.Component:
    """A component memo named the same as memos in the sibling fixtures.

    Args:
        title: The title to render.

    Returns:
        A text component.
    """
    return rx.text("module_a:", title)


@rx.memo
def my_value(x: rx.Var[int]) -> rx.Var[str]:
    """A function memo named the same as one in ``module_b``.

    Args:
        x: The value to format.

    Returns:
        A prefixed string var.
    """
    return "a:" + x.to(str)
