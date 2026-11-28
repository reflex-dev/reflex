"""Tests for reflex_components_ui.layout.container."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_container_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A container centers an inner div of its default width, with padding."""
    component = rx.ui.container("a")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_4d7dc9707b_c"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_5cfb91b5e6_c"],
                "children": [{"contents": '"a"'}],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "display": "flex",
            "boxSizing": "border-box",
            "flexDirection": "column",
            "alignItems": "center",
            "flexShrink": "0",
            "flexGrow": "1",
            "paddingTop": "16px",
            "paddingRight": "16px",
            "paddingBottom": "16px",
            "paddingLeft": "16px",
        },
        {"width": "100%", "maxWidth": "880px"},
    ]


def test_container_sizes(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """The size bounds the inner div, and the padding is the element's."""
    component = rx.ui.container(
        "a", size=rx.breakpoints(initial="1", md="4"), padding="0px", id="page"
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_5ce2c30d05_c", 'id:"page"', "ref:ref_page"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_974d132e83_c"],
                "children": [{"contents": '"a"'}],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "display": "flex",
            "boxSizing": "border-box",
            "flexDirection": "column",
            "alignItems": "center",
            "flexShrink": "0",
            "flexGrow": "1",
            "paddingTop": "0px",
            "paddingRight": "0px",
            "paddingBottom": "0px",
            "paddingLeft": "0px",
        },
        {
            "width": "100%",
            "maxWidth": {"default": "448px", "@media (min-width: 1024px)": "1136px"},
        },
    ]
