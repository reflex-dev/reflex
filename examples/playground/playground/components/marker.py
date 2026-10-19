"""The leaf component the hot reload benchmarks rewrite."""

import reflex as rx

LEAF_MARKER = "m-initial-leaf"  # bench:hmr-target leaf


def marker() -> rx.Component:
    """Render the leaf hot reload marker.

    Returns:
        A span holding the leaf marker.
    """
    return rx.el.span(LEAF_MARKER, id="bench-marker-leaf")
