"""Tests for reflex_components_ui.components.icon_button."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.components.component import Component
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_icon_button_from_a_name(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
    compiled: Callable[[Component], Component],
):
    """The name of an icon is the icon, and the button is as wide as it is tall."""
    component = compiled(rx.ui.icon_button("plus"))
    assert component.render() == {
        "name": '"button"',
        "props": ["className:sx_afda1d7c43_c"],
        "children": [{"name": "LucidePlus", "props": [], "children": []}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "6px",
            "paddingRight": "6px",
            "paddingBottom": "6px",
            "paddingLeft": "6px",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "backgroundColor": {
                "default": "var(--accent-9)",
                "@media (hover: hover)": {":hover:not(:active)": "var(--accent-10)"},
                "[data-state='open']": "var(--accent-10)",
                ":active:not([data-state='open'])": "var(--accent-10)",
                "[data-disabled]": "var(--gray-a3)",
            },
            "backgroundImage": "none",
            "appearance": "none",
            "boxSizing": "border-box",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "textTransform": "inherit",
            "textIndent": "initial",
            "textShadow": "inherit",
            "wordSpacing": "inherit",
            "cursor": {
                "default": "inherit",
                ":where(button)": "var(--cursor-button)",
                ":any-link": "var(--cursor-link)",
                "[data-disabled]": "var(--cursor-disabled)",
            },
            "outlineStyle": {
                "default": "none",
                "@media (pointer: coarse)": {
                    ":active:not([data-state='open'], [data-disabled], :focus-visible)": "solid"
                },
                ":focus-visible:not([data-disabled])": "solid",
            },
            "WebkitTapHighlightColor": "transparent",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "flexShrink": 0,
            "userSelect": "none",
            "verticalAlign": "top",
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "center",
            "--spinner-opacity": {"[data-disabled]": "1"},
            "--base-button-classic-active-padding-top": "2px",
            "--base-button-height": "var(--space-6)",
            "borderRadius": "max(var(--radius-2), var(--radius-full))",
            "color": {
                "default": "var(--accent-contrast)",
                "[data-disabled]": "var(--gray-a8)",
            },
            "filter": {
                ":active:not([data-state='open'])": "var(--rx-if-light, brightness(0.92) "
                "saturate(1.1)) var(--rx-if-dark, "
                "brightness(1.08))",
                "[data-disabled]": "none",
            },
            "outlineWidth": {
                "@media (pointer: coarse)": {
                    ":active:not([data-state='open'], [data-disabled], :focus-visible)": "0.5em"
                },
                ":focus-visible:not([data-disabled])": "2px",
            },
            "outlineColor": {
                "@media (pointer: coarse)": {
                    ":active:not([data-state='open'], [data-disabled], :focus-visible)": "var(--accent-a4)"
                },
                ":focus-visible:not([data-disabled])": "var(--focus-8)",
            },
            "outlineOffset": {
                "@media (pointer: coarse)": {
                    ":active:not([data-state='open'], [data-disabled], :focus-visible)": "0"
                },
                ":focus-visible:not([data-disabled])": "2px",
            },
            "height": "var(--base-button-height)",
            "width": "var(--base-button-height)",
        }
    ]


def test_icon_button_size_sizes_the_icon(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
    compiled: Callable[[Component], Component],
):
    """The size of the button gives the icon its size."""
    component = compiled(rx.ui.icon_button(rx.icon("trash"), size="3", variant="soft"))
    assert component.render() == {
        "name": '"button"',
        "props": ["className:sx_46971f9a00_c"],
        "children": [{"name": "LucideTrash", "props": ["size:36"], "children": []}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "6px",
            "paddingRight": "6px",
            "paddingBottom": "6px",
            "paddingLeft": "6px",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "backgroundColor": {
                "default": "var(--accent-a3)",
                "@media (hover: hover)": {":hover:not(:active)": "var(--accent-a4)"},
                "[data-state='open']": "var(--accent-a4)",
                ":active:not([data-state='open'])": "var(--accent-a5)",
                "[data-disabled]": "var(--gray-a3)",
            },
            "backgroundImage": "none",
            "appearance": "none",
            "boxSizing": "border-box",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "textTransform": "inherit",
            "textIndent": "initial",
            "textShadow": "inherit",
            "wordSpacing": "inherit",
            "cursor": {
                "default": "inherit",
                ":where(button)": "var(--cursor-button)",
                ":any-link": "var(--cursor-link)",
                "[data-disabled]": "var(--cursor-disabled)",
            },
            "outlineStyle": {"default": "none", ":focus-visible": "solid"},
            "WebkitTapHighlightColor": "transparent",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "flexShrink": 0,
            "userSelect": "none",
            "verticalAlign": "top",
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "center",
            "--spinner-opacity": {"[data-disabled]": "1"},
            "--base-button-classic-active-padding-top": "2px",
            "--base-button-height": "var(--space-7)",
            "borderRadius": "max(var(--radius-3), var(--radius-full))",
            "color": {
                "default": "var(--accent-a11)",
                "[data-disabled]": "var(--gray-a8)",
            },
            "outlineWidth": {":focus-visible": "2px"},
            "outlineColor": {":focus-visible": "var(--accent-8)"},
            "outlineOffset": {":focus-visible": "-1px"},
            "height": "var(--base-button-height)",
            "width": "var(--base-button-height)",
        }
    ]


def test_icon_button_ghost(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
    compiled: Callable[[Component], Component],
):
    """A ghost icon button has the padding of the wrapper over the one of its size."""
    component = compiled(rx.ui.icon_button("plus", variant="ghost", size="2"))
    assert declared_styles(component) == [
        {
            "marginTop": "calc(0px - calc(var(--space-1) * 1.5))",
            "marginRight": "calc(0px - calc(var(--space-1) * 1.5))",
            "marginBottom": "calc(0px - calc(var(--space-1) * 1.5))",
            "marginLeft": "calc(0px - calc(var(--space-1) * 1.5))",
            "paddingTop": "6px",
            "paddingRight": "6px",
            "paddingBottom": "6px",
            "paddingLeft": "6px",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "backgroundColor": {
                "default": "transparent",
                "@media (hover: hover)": {":hover:not(:active)": "var(--accent-a3)"},
                "[data-state='open']": "var(--accent-a3)",
                ":active:not([data-state='open'])": "var(--accent-a4)",
                "[data-disabled]": "transparent",
            },
            "backgroundImage": "none",
            "appearance": "none",
            "boxSizing": "content-box",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "textTransform": "inherit",
            "textIndent": "initial",
            "textShadow": "inherit",
            "wordSpacing": "inherit",
            "cursor": {
                "default": "inherit",
                ":where(button)": "var(--cursor-button)",
                ":any-link": "var(--cursor-link)",
                "[data-disabled]": "var(--cursor-disabled)",
            },
            "outlineStyle": {"default": "none", ":focus-visible": "solid"},
            "WebkitTapHighlightColor": "transparent",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "flexShrink": 0,
            "userSelect": "none",
            "verticalAlign": "top",
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "center",
            "--spinner-opacity": {"[data-disabled]": "1"},
            "--base-button-classic-active-padding-top": "2px",
            "--base-button-height": "var(--space-6)",
            "borderRadius": "max(var(--radius-2), var(--radius-full))",
            "color": {
                "default": "var(--accent-a11)",
                "[data-disabled]": "var(--gray-a8)",
            },
            "outlineWidth": {":focus-visible": "2px"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "outlineOffset": {":focus-visible": "-1px"},
            "height": "fit-content",
        }
    ]


def test_icon_button_needs_an_icon():
    """Without a child there is nothing to show."""
    with pytest.raises(ValueError, match="IconButton requires a child icon") as raised:
        rx.ui.icon_button()
    assert str(raised.value) == (
        "IconButton requires a child icon. Pass a string as the first child or a "
        "rx.icon."
    )
