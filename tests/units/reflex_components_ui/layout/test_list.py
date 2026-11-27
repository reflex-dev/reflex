"""Tests for reflex_components_ui.layout.list."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_list_unordered(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """An unordered list is a ul of items with discs and room for them."""
    component = rx.ui.list.unordered(items=["a", "b"])
    assert component.render() == {
        "name": '"ul"',
        "props": ["className:sx_9d24074fc7_c"],
        "children": [
            {"name": '"li"', "props": [], "children": [{"contents": '"a"'}]},
            {"name": '"li"', "props": [], "children": [{"contents": '"b"'}]},
        ],
    }
    assert declared_styles(component) == [
        {"listStyleType": "disc", "marginLeft": "1.5rem"},
        {},
        {},
    ]


def test_list_ordered(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """An ordered list is an ol with numbers, or the marker it is given."""
    component = rx.ui.list.ordered(
        rx.ui.list.item("a", id="first"), list_style_type="upper-roman", margin_left="0"
    )
    assert component.render() == {
        "name": '"ol"',
        "props": ["className:sx_c4dab3f068_c"],
        "children": [
            {
                "name": '"li"',
                "props": ['id:"first"', "ref:ref_first"],
                "children": [{"contents": '"a"'}],
            }
        ],
    }
    assert declared_styles(component) == [
        {"listStyleType": "upper-roman", "marginLeft": "0"},
        {},
    ]


def test_list_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A plain list has no marker and no indent, and its marker wins over the style."""
    component = rx.ui.list(
        rx.ui.list.item("a"), style={"list_style_type": "disc", "color": "red"}
    )
    assert component.render() == {
        "name": '"ul"',
        "props": ["className:sx_98c5add4ad_c"],
        "children": [{"name": '"li"', "props": [], "children": [{"contents": '"a"'}]}],
    }
    assert declared_styles(component) == [{"color": "red", "listStyleType": "none"}, {}]


def test_list_item(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Text inside an item is a span, and an icon is inline."""
    component = rx.ui.list.item(rx.icon("check"), rx.ui.text("done"))
    assert component.render() == {
        "name": '"li"',
        "props": [],
        "children": [
            {
                "name": "LucideCheck",
                "props": ['css:({ ["display"] : "inline" })'],
                "children": [],
            },
            {
                "name": '"span"',
                "props": ["className:sx_af8fa2456e_c"],
                "children": [{"contents": '"done"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {},
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
        },
    ]
