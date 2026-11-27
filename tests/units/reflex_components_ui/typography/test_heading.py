"""Tests for reflex_components_ui.typography.heading."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_heading_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A heading is an h1 of the sixth size."""
    component = rx.ui.heading("a")
    assert component.render() == {
        "name": '"h1"',
        "props": ["className:sx_3cd9045b38_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "--leading-trim-start": "var(--heading-leading-trim-start)",
            "--leading-trim-end": "var(--heading-leading-trim-end)",
            "fontFamily": "var(--heading-font-family)",
            "fontStyle": "var(--heading-font-style)",
            "fontWeight": "var(--font-weight-bold)",
            "lineHeight": "var(--line-height)",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "fontSize": "calc(var(--font-size-6) * var(--heading-font-size-adjust))",
            "--line-height": "var(--heading-line-height-6)",
            "letterSpacing": "calc(var(--letter-spacing-6) + var(--heading-letter-spacing))",
        }
    ]


def test_heading_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Its level is the tag, and its props are styles."""
    component = rx.ui.heading(
        "a",
        as_="h3",
        size="8",
        weight="medium",
        align="right",
        trim="start",
        color_scheme="gray",
        high_contrast=True,
    )
    assert component.render() == {
        "name": '"h3"',
        "props": ['className:sx_c91e482fa5_c + " " + reflexUIClasses_fe8edd03f8'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "--leading-trim-start": "var(--heading-leading-trim-start)",
            "--leading-trim-end": "var(--heading-leading-trim-end)",
            "fontFamily": "var(--heading-font-family)",
            "fontStyle": "var(--heading-font-style)",
            "fontWeight": "var(--font-weight-medium)",
            "lineHeight": "var(--line-height)",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": {
                "default": "0",
                "::before": "calc(var(--leading-trim-start, "
                "var(--default-leading-trim-start)) - "
                "var(--line-height, calc(1em * "
                "var(--default-line-height))) / 2)",
            },
            "marginLeft": "0",
            "fontSize": "calc(var(--font-size-8) * var(--heading-font-size-adjust))",
            "--line-height": "var(--heading-line-height-8)",
            "letterSpacing": "calc(var(--letter-spacing-8) + var(--heading-letter-spacing))",
            "textAlign": "right",
            "content": {"::before": "''", "::after": "none"},
            "display": {"::before": "table"},
            "--rx-accent-text": "var(--accent-12)",
            "color": "var(--accent-12)",
        }
    ]


def test_heading_fallback_tag(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A tag that is not a heading renders an h1."""
    component = rx.ui.heading("a", as_="div", size=rx.breakpoints(sm="9"))
    assert component.render() == {
        "name": '"h1"',
        "props": ["className:sx_64062b0d12_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "--leading-trim-start": "var(--heading-leading-trim-start)",
            "--leading-trim-end": "var(--heading-leading-trim-end)",
            "fontFamily": "var(--heading-font-family)",
            "fontStyle": "var(--heading-font-style)",
            "fontWeight": "var(--font-weight-bold)",
            "lineHeight": "var(--line-height)",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "fontSize": {
                "default": "calc(var(--font-size-6) * var(--heading-font-size-adjust))",
                "@media (min-width: 768px)": "calc(var(--font-size-9) * "
                "var(--heading-font-size-adjust))",
            },
            "--line-height": {
                "default": "var(--heading-line-height-6)",
                "@media (min-width: 768px)": "var(--heading-line-height-9)",
            },
            "letterSpacing": {
                "default": "calc(var(--letter-spacing-6) + "
                "var(--heading-letter-spacing))",
                "@media (min-width: 768px)": "calc(var(--letter-spacing-9) + "
                "var(--heading-letter-spacing))",
            },
        }
    ]
