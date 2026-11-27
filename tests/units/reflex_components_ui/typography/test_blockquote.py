"""Tests for reflex_components_ui.typography.blockquote."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_blockquote_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A block quotation is text with a rule in the accent beside it."""
    component = rx.ui.blockquote("a")
    assert component.render() == {
        "name": '"blockquote"',
        "props": ["className:sx_2166c3832e_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "boxSizing": "border-box",
            "borderLeftWidth": "max(var(--space-1), 0.25em)",
            "borderLeftStyle": "solid",
            "borderLeftColor": "var(--accent-a6)",
            "paddingLeft": "min(var(--space-5), max(var(--space-3), 0.5em))",
        }
    ]


def test_blockquote_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """It has the size, weight and color of text."""
    component = rx.ui.blockquote(
        "a",
        size="4",
        weight="light",
        color_scheme="plum",
        high_contrast=True,
        cite="https://example.com",
    )
    assert component.render() == {
        "name": '"blockquote"',
        "props": [
            'cite:"https://example.com"',
            'className:sx_a40e05b616_c + " " + reflexUIClasses_3c6adfa0ad',
        ],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "boxSizing": "border-box",
            "borderLeftWidth": "max(var(--space-1), 0.25em)",
            "borderLeftStyle": "solid",
            "borderLeftColor": "var(--accent-a6)",
            "paddingLeft": "min(var(--space-5), max(var(--space-3), 0.5em))",
            "fontSize": "var(--font-size-4)",
            "--line-height": "var(--line-height-4)",
            "--letter-spacing": "var(--letter-spacing-4)",
            "fontWeight": "var(--font-weight-light)",
            "--rx-accent-text": "var(--accent-12)",
            "color": "var(--accent-12)",
        }
    ]
