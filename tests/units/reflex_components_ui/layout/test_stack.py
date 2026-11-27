"""Tests for reflex_components_ui.layout.stack."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_stack_stack(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A stack has a gap and aligns its children at the start."""
    component = rx.ui.stack("a", "b")
    assert component.render() == {
        "name": '"div"',
        "props": ['className:"rx-Stack " + sx_e8554125f7_c'],
        "children": [{"contents": '"a"'}, {"contents": '"b"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "justifyContent": "flex-start",
            "alignItems": "flex-start",
            "rowGap": "var(--space-3)",
            "columnGap": "var(--space-3)",
        }
    ]


def test_stack_hstack(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A horizontal stack is a row, whatever the class names it is given."""
    component = rx.ui.hstack("a", class_name="toolbar", spacing="1")
    assert component.render() == {
        "name": '"div"',
        "props": ['className:"rx-Stack toolbar " + sx_ddd1ab0711_c'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "justifyContent": "flex-start",
            "alignItems": "flex-start",
            "flexDirection": "row",
            "rowGap": "var(--space-1)",
            "columnGap": "var(--space-1)",
        }
    ]


def test_stack_vstack(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A vertical stack is a column."""
    component = rx.ui.vstack(
        "a", align="center", direction=rx.breakpoints(initial="column", sm="row")
    )
    assert component.render() == {
        "name": '"div"',
        "props": ['className:"rx-Stack " + sx_f669e55d47_c'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "justifyContent": "flex-start",
            "alignItems": "center",
            "flexDirection": {"default": "column", "@media (min-width: 768px)": "row"},
            "rowGap": "var(--space-3)",
            "columnGap": "var(--space-3)",
        }
    ]
