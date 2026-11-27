"""Tests for reflex_components_ui.layout.grid."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_grid_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A grid is a div with one column until it is told otherwise."""
    component = rx.ui.grid("a", "b")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_c885f4149b_c"],
        "children": [{"contents": '"a"'}, {"contents": '"b"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "grid",
            "alignItems": "stretch",
            "justifyContent": "flex-start",
            "gridTemplateColumns": "minmax(0, 1fr)",
            "gridTemplateRows": "none",
        }
    ]


def test_grid_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Counts become tracks of equal size, anything else is CSS."""
    component = rx.ui.grid(
        "a",
        columns=rx.breakpoints(initial="1", sm="3"),
        rows="repeat(2, 64px)",
        flow="row-dense",
        align="end",
        justify="center",
        spacing="2",
        spacing_x="4",
        spacing_y="1",
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_7fdc4cc3b1_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "grid",
            "alignItems": "flex-end",
            "justifyContent": "center",
            "gridTemplateColumns": {
                "default": "repeat(1, minmax(0, 1fr))",
                "@media (min-width: 768px)": "repeat(3, minmax(0, 1fr))",
            },
            "gridTemplateRows": "repeat(2, 64px)",
            "gridAutoFlow": "row dense",
            "rowGap": "var(--space-1)",
            "columnGap": "var(--space-4)",
        }
    ]
