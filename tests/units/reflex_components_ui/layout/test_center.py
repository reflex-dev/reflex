"""Tests for reflex_components_ui.layout.center."""

from collections.abc import Callable
from typing import Any

from reflex_base.components.component import Component
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_center_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A center is a flex container, before the compile adds its style."""
    component = rx.ui.center("a")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_78b49527aa_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {"boxSizing": "border-box", "display": "flex", "justifyContent": "flex-start"}
    ]


def test_center_compiled(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
    compiled: Callable[[Component], Component],
):
    """The compile centers the content, over the props of the element."""
    component = compiled(rx.ui.center("a", align="start", spacing="2"))
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_58f475335d_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "justifyContent": "center",
            "alignItems": "center",
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
        }
    ]
