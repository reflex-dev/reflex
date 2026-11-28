"""Tests for reflex_components_ui.components.inset."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_inset_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """An inset reaches every edge of its container."""
    component = rx.ui.inset("a")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_c190e59d1d_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "overflowX": "hidden",
            "overflowY": "hidden",
            "--inset-border-radius-calc": "calc(var(--inset-border-radius, 0px) - "
            "var(--inset-border-width, 0px))",
            "--inset-padding-top-calc": "var(--inset-padding-top, 0px)",
            "--inset-padding-right-calc": "var(--inset-padding-right, 0px)",
            "--inset-padding-bottom-calc": "var(--inset-padding-bottom, 0px)",
            "--inset-padding-left-calc": "var(--inset-padding-left, 0px)",
            "marginTop": "calc(0px - var(--inset-padding-top-calc))",
            "marginRight": "calc(0px - var(--inset-padding-right-calc))",
            "marginBottom": "calc(0px - var(--inset-padding-bottom-calc))",
            "marginLeft": "calc(0px - var(--inset-padding-left-calc))",
            "borderTopLeftRadius": "var(--inset-border-radius-calc)",
            "borderTopRightRadius": "var(--inset-border-radius-calc)",
            "borderBottomLeftRadius": "var(--inset-border-radius-calc)",
            "borderBottomRightRadius": "var(--inset-border-radius-calc)",
        }
    ]


def test_inset_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A side, the border, and the padding of the container."""
    component = rx.ui.inset(
        "a", side="top", clip="padding-box", pb="current", px="0", id="cover"
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_5dd6cd8662_c", 'id:"cover"', "ref:ref_cover"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "overflowX": "hidden",
            "overflowY": "hidden",
            "--inset-border-radius-calc": "var(--inset-border-radius, 0px)",
            "--inset-padding-top-calc": "calc(var(--inset-padding-top, 0px) + "
            "var(--inset-border-width, 0px))",
            "--inset-padding-right-calc": "calc(var(--inset-padding-right, 0px) + "
            "var(--inset-border-width, 0px))",
            "--inset-padding-bottom-calc": "calc(var(--inset-padding-bottom, 0px) + "
            "var(--inset-border-width, 0px))",
            "--inset-padding-left-calc": "calc(var(--inset-padding-left, 0px) + "
            "var(--inset-border-width, 0px))",
            "marginTop": "calc(0px - var(--inset-padding-top-calc))",
            "marginRight": "calc(0px - var(--inset-padding-right-calc))",
            "marginBottom": "0px",
            "marginLeft": "calc(0px - var(--inset-padding-left-calc))",
            "borderTopLeftRadius": "var(--inset-border-radius-calc)",
            "borderTopRightRadius": "var(--inset-border-radius-calc)",
            "borderBottomLeftRadius": "0px",
            "borderBottomRightRadius": "0px",
            "paddingLeft": "0",
            "paddingRight": "0",
            "paddingBottom": "var(--inset-padding-bottom)",
        }
    ]
