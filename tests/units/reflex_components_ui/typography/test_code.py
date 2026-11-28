"""Tests for reflex_components_ui.typography.code."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_code_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Code is soft unless told otherwise, and says so to a link around it."""
    component = rx.ui.code("a")
    assert component.render() == {
        "name": '"code"',
        "props": ["className:sx_13e8bd16fd_c", '"data-variant":"soft"'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "--code-variant-font-size-adjust": "calc(var(--code-font-size-adjust) * 0.95)",
            "fontFamily": "var(--code-font-family)",
            "fontSize": "calc(var(--code-variant-font-size-adjust) * 1em)",
            "fontStyle": "var(--code-font-style)",
            "fontWeight": "var(--code-font-weight)",
            "lineHeight": "1.25",
            "letterSpacing": "calc(var(--code-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
            "borderRadius": "calc((0.5px + 0.2em) * var(--radius-factor))",
            "boxSizing": "border-box",
            "paddingTop": "var(--code-padding-top)",
            "paddingLeft": "var(--code-padding-left)",
            "paddingBottom": "var(--code-padding-bottom)",
            "paddingRight": "var(--code-padding-right)",
            "height": "fit-content",
            "isolation": "var(--rx-link-code-isolation, auto)",
            "backgroundColor": {
                "default": "var(--accent-a3)",
                "@media (hover: hover)": {
                    ":hover": "var(--rx-link-code-soft, var(--accent-a3))"
                },
            },
            "color": "var(--accent-a11)",
        }
    ]


def test_code_ghost(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Ghost code has no box, and a color only when it is given one."""
    component = rx.ui.box(
        rx.ui.code("a", variant="ghost"),
        rx.ui.code("b", variant="ghost", color_scheme="ruby", high_contrast=True),
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_b26ac4fb71_c"],
        "children": [
            {
                "name": '"code"',
                "props": ["className:sx_35379f6a4b_c", '"data-variant":"ghost"'],
                "children": [{"contents": '"a"'}],
            },
            {
                "name": '"code"',
                "props": [
                    'className:sx_83425e1e1d_c + " " + reflexUIClasses_e201574881',
                    '"data-variant":"ghost"',
                ],
                "children": [{"contents": '"b"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {"boxSizing": "border-box", "display": "block"},
        {
            "--code-variant-font-size-adjust": "var(--code-font-size-adjust)",
            "fontFamily": "var(--code-font-family)",
            "fontSize": "calc(var(--code-variant-font-size-adjust) * 1em)",
            "fontStyle": "var(--code-font-style)",
            "fontWeight": "var(--code-font-weight)",
            "lineHeight": "1.25",
            "letterSpacing": "calc(var(--code-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
            "borderRadius": "calc((0.5px + 0.2em) * var(--radius-factor))",
            "boxSizing": "border-box",
            "paddingTop": "0",
            "paddingLeft": "0",
            "paddingBottom": "0",
            "paddingRight": "0",
            "height": "fit-content",
        },
        {
            "--code-variant-font-size-adjust": "var(--code-font-size-adjust)",
            "fontFamily": "var(--code-font-family)",
            "fontSize": "calc(var(--code-variant-font-size-adjust) * 1em)",
            "fontStyle": "var(--code-font-style)",
            "fontWeight": "var(--code-font-weight)",
            "lineHeight": "1.25",
            "letterSpacing": "calc(var(--code-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
            "borderRadius": "calc((0.5px + 0.2em) * var(--radius-factor))",
            "boxSizing": "border-box",
            "paddingTop": "0",
            "paddingLeft": "0",
            "paddingBottom": "0",
            "paddingRight": "0",
            "height": "fit-content",
            "--rx-accent-text": "var(--accent-12)",
            "color": "var(--accent-12)",
        },
    ]


def test_code_solid(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Solid code in high contrast, at a size."""
    component = rx.ui.code(
        "a", variant="solid", high_contrast=True, size="2", weight="bold"
    )
    assert component.render() == {
        "name": '"code"',
        "props": ["className:sx_8d89af6b0e_c", '"data-variant":"solid"'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "--code-variant-font-size-adjust": "calc(var(--code-font-size-adjust) * 0.95)",
            "fontFamily": "var(--code-font-family)",
            "fontSize": "calc(var(--font-size-2) * var(--code-variant-font-size-adjust))",
            "fontStyle": "var(--code-font-style)",
            "fontWeight": "var(--font-weight-bold)",
            "lineHeight": "var(--line-height-2)",
            "letterSpacing": "calc(var(--code-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
            "borderRadius": "calc((0.5px + 0.2em) * var(--radius-factor))",
            "boxSizing": "border-box",
            "paddingTop": "var(--code-padding-top)",
            "paddingLeft": "var(--code-padding-left)",
            "paddingBottom": "var(--code-padding-bottom)",
            "paddingRight": "var(--code-padding-right)",
            "height": "fit-content",
            "--letter-spacing": "var(--letter-spacing-2)",
            "isolation": "var(--rx-link-code-isolation, auto)",
            "backgroundColor": {
                "default": "var(--accent-12)",
                "::selection": "var(--accent-a11)",
            },
            "color": {"default": "var(--accent-1)", "::selection": "var(--accent-1)"},
            "filter": {
                "@media (hover: hover)": {":hover": "var(--rx-link-code-filter, none)"}
            },
        }
    ]


def test_code_outline(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Outlined code, and a variant Radix Themes does not have for code."""
    component = rx.ui.box(
        rx.ui.code("a", variant="outline"), rx.ui.code("b", variant="surface")
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_b26ac4fb71_c"],
        "children": [
            {
                "name": '"code"',
                "props": ["className:sx_ab161c22a8_c", '"data-variant":"outline"'],
                "children": [{"contents": '"a"'}],
            },
            {
                "name": '"code"',
                "props": ["className:sx_13e8bd16fd_c", '"data-variant":"surface"'],
                "children": [{"contents": '"b"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {"boxSizing": "border-box", "display": "block"},
        {
            "--code-variant-font-size-adjust": "calc(var(--code-font-size-adjust) * 0.95)",
            "fontFamily": "var(--code-font-family)",
            "fontSize": "calc(var(--code-variant-font-size-adjust) * 1em)",
            "fontStyle": "var(--code-font-style)",
            "fontWeight": "var(--code-font-weight)",
            "lineHeight": "1.25",
            "letterSpacing": "calc(var(--code-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
            "borderRadius": "calc((0.5px + 0.2em) * var(--radius-factor))",
            "boxSizing": "border-box",
            "paddingTop": "var(--code-padding-top)",
            "paddingLeft": "var(--code-padding-left)",
            "paddingBottom": "var(--code-padding-bottom)",
            "paddingRight": "var(--code-padding-right)",
            "height": "fit-content",
            "isolation": "var(--rx-link-code-isolation, auto)",
            "boxShadow": "inset 0 0 0 max(1px, 0.033em) var(--accent-a8)",
            "color": "var(--accent-a11)",
            "backgroundColor": {
                "@media (hover: hover)": {
                    ":hover": "var(--rx-link-code-outline, transparent)"
                }
            },
        },
        {
            "--code-variant-font-size-adjust": "calc(var(--code-font-size-adjust) * 0.95)",
            "fontFamily": "var(--code-font-family)",
            "fontSize": "calc(var(--code-variant-font-size-adjust) * 1em)",
            "fontStyle": "var(--code-font-style)",
            "fontWeight": "var(--code-font-weight)",
            "lineHeight": "1.25",
            "letterSpacing": "calc(var(--code-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
            "borderRadius": "calc((0.5px + 0.2em) * var(--radius-factor))",
            "boxSizing": "border-box",
            "paddingTop": "var(--code-padding-top)",
            "paddingLeft": "var(--code-padding-left)",
            "paddingBottom": "var(--code-padding-bottom)",
            "paddingRight": "var(--code-padding-right)",
            "height": "fit-content",
            "isolation": "var(--rx-link-code-isolation, auto)",
            "backgroundColor": {
                "default": "var(--accent-a3)",
                "@media (hover: hover)": {
                    ":hover": "var(--rx-link-code-soft, var(--accent-a3))"
                },
            },
            "color": "var(--accent-a11)",
        },
    ]
