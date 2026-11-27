"""Tests for reflex_components_ui.components.scroll_area."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_scroll_area_plain(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A scroll area scrolls both ways, around a block that holds its children."""
    component = rx.ui.scroll_area(rx.el.p("One"), rx.el.p("Two"), id="area")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_d0de57eb68_c", 'id:"area"', "ref:ref_area"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_b06d947c7c_c"],
                "children": [
                    {"name": '"p"', "props": [], "children": [{"contents": '"One"'}]},
                    {"name": '"p"', "props": [], "children": [{"contents": '"Two"'}]},
                ],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexDirection": "column",
            "position": "relative",
            "width": "100%",
            "height": "100%",
            "scrollbarWidth": "thin",
            "scrollbarColor": "var(--gray-a8) var(--gray-a3)",
            "outlineWidth": {":focus-visible": "2px"},
            "outlineStyle": {":focus-visible": "solid"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "outlineOffset": {":focus-visible": "-2px"},
            "overflowX": "auto",
            "overflowY": "auto",
            "overscrollBehaviorX": "contain",
        },
        {
            "boxSizing": "border-box",
            "display": "block",
            "width": "fit-content",
            "minWidth": "100%",
            "flexGrow": 1,
        },
    ]


def test_scroll_area_vertical_always(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """One scrollbar clips the other axis, and always shows it."""
    component = rx.ui.scroll_area(
        "Text",
        scrollbars="vertical",
        type="always",
        scroll_hide_delay=100,
        height="120px",
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_b6352d4ad5_c"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_b06d947c7c_c"],
                "children": [{"contents": '"Text"'}],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexDirection": "column",
            "position": "relative",
            "width": "100%",
            "height": "120px",
            "scrollbarWidth": "thin",
            "scrollbarColor": "var(--gray-a8) var(--gray-a3)",
            "outlineWidth": {":focus-visible": "2px"},
            "outlineStyle": {":focus-visible": "solid"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "outlineOffset": {":focus-visible": "-2px"},
            "overflowX": "hidden",
            "overflowY": "scroll",
        },
        {
            "boxSizing": "border-box",
            "display": "block",
            "width": "fit-content",
            "minWidth": "100%",
            "flexGrow": 1,
        },
    ]


def test_scroll_area_horizontal(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A horizontal area keeps a swipe from leaving the page."""
    component = rx.ui.scroll_area("Text", scrollbars="horizontal", type="hover")
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexDirection": "column",
            "position": "relative",
            "width": "100%",
            "height": "100%",
            "scrollbarWidth": "thin",
            "scrollbarColor": "var(--gray-a8) var(--gray-a3)",
            "outlineWidth": {":focus-visible": "2px"},
            "outlineStyle": {":focus-visible": "solid"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "outlineOffset": {":focus-visible": "-2px"},
            "overflowX": "auto",
            "overflowY": "hidden",
            "overscrollBehaviorX": "contain",
        },
        {
            "boxSizing": "border-box",
            "display": "block",
            "width": "fit-content",
            "minWidth": "100%",
            "flexGrow": 1,
        },
    ]
