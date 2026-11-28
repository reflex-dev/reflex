"""Tests for reflex_components_ui.layout.flex."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_flex_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A flex container is a div that lays its children out in a row."""
    component = rx.ui.flex("a", "b")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_78b49527aa_c"],
        "children": [{"contents": '"a"'}, {"contents": '"b"'}],
    }
    assert declared_styles(component) == [
        {"boxSizing": "border-box", "display": "flex", "justifyContent": "flex-start"}
    ]


def test_flex_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Its props are styles, on the breakpoints of Radix Themes."""
    component = rx.ui.flex(
        "a",
        direction=rx.breakpoints(initial="column", md="row"),
        align="center",
        justify="between",
        wrap="wrap",
        spacing="3",
        id="row",
        title="A row",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_a66dcbf62c_c",
            'id:"row"',
            "ref:ref_row",
            'title:"A row"',
        ],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "flexDirection": {"default": "column", "@media (min-width: 1024px)": "row"},
            "rowGap": "var(--space-3)",
            "columnGap": "var(--space-3)",
            "flexWrap": "wrap",
        }
    ]


def test_flex_style_over_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """The style of the element wins over its props."""
    component = rx.ui.flex(
        "a", spacing="3", gap="1px", direction="column", style={"flex_direction": "row"}
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_1126f0dad7_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "justifyContent": "flex-start",
            "flexDirection": "row",
            "rowGap": "1px",
            "columnGap": "1px",
        }
    ]
