"""Module B: defines a memo named ``badge`` (same name also exists in mod_a)."""

import reflex as rx


@rx.memo
def badge(label: rx.Var[str]) -> rx.Component:
    """Badge variant B.

    Args:
        label: Text shown in the badge.

    Returns:
        The badge component.
    """
    return rx.el.span("B:", label, class_name="badge-b")
