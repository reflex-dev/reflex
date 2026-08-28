"""Module A: defines a memo named ``badge`` (same name also exists in mod_b)."""

import reflex as rx


@rx.memo
def badge(label: rx.Var[str]) -> rx.Component:
    """Badge variant A.

    Args:
        label: Text shown in the badge.

    Returns:
        The badge component.
    """
    return rx.el.span("A:", label, class_name="badge-a")
