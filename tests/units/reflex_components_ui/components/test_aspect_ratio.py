"""Tests for reflex_components_ui.components.aspect_ratio."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_aspect_ratio_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """An aspect ratio is a frame as high as it is wide, with the content filling it."""
    component = rx.ui.aspect_ratio("a")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_7e9d0745eb_c", '"data-radix-aspect-ratio-wrapper":""'],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_f0e83cb220_c"],
                "children": [{"contents": '"a"'}],
            }
        ],
    }
    assert declared_styles(component) == [
        {"position": "relative", "width": "100%", "paddingBottom": "100.0%"},
        {"position": "absolute", "top": "0", "right": "0", "bottom": "0", "left": "0"},
    ]


def test_aspect_ratio_ratio(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """The ratio sets the height of the frame, and the props go to the content."""
    component = rx.ui.aspect_ratio(
        "a", ratio=16 / 9, id="video", style={"border_radius": "4px"}
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_29d4184c5f_c", '"data-radix-aspect-ratio-wrapper":""'],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_75437de2d8_c", 'id:"video"', "ref:ref_video"],
                "children": [{"contents": '"a"'}],
            }
        ],
    }
    assert declared_styles(component) == [
        {"position": "relative", "width": "100%", "paddingBottom": "56.25%"},
        {
            "position": "absolute",
            "top": "0",
            "right": "0",
            "bottom": "0",
            "left": "0",
            "borderTopLeftRadius": "4px",
            "borderTopRightRadius": "4px",
            "borderBottomRightRadius": "4px",
            "borderBottomLeftRadius": "4px",
        },
    ]
