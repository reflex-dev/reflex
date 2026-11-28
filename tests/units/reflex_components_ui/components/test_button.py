"""Tests for reflex_components_ui.components.button."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.components.dynamic import _RENDERING_DYNAMIC_COMPONENT
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import Keyframes, StyleError
from reflex_components_ui.themes import ThemeError

import reflex as rx

# What each leaf of a spinner declares.
LEAF: dict[str, Any] = {
    "position": "absolute",
    "top": "0",
    "left": "calc(50% - 12.5% / 2)",
    "width": {"default": "12.5%", "::before": "100%"},
    "height": {"default": "100%", "::before": "30%"},
    "animationName": Keyframes(
        ('{"from": {"opacity": 1}, "to": {"opacity": 0.25}}',), ()
    ),
    "animationDuration": "var(--spinner-animation-duration, 800ms)",
    "animationTimingFunction": "linear",
    "animationIterationCount": "infinite",
    "transform": {
        ":nth-child(1)": "rotate(0deg)",
        ":nth-child(2)": "rotate(45deg)",
        ":nth-child(3)": "rotate(90deg)",
        ":nth-child(4)": "rotate(135deg)",
        ":nth-child(5)": "rotate(180deg)",
        ":nth-child(6)": "rotate(225deg)",
        ":nth-child(7)": "rotate(270deg)",
        ":nth-child(8)": "rotate(315deg)",
    },
    "animationDelay": {
        ":nth-child(1)": "calc(-8 / 8 * var(--spinner-animation-duration, 800ms))",
        ":nth-child(2)": "calc(-7 / 8 * var(--spinner-animation-duration, 800ms))",
        ":nth-child(3)": "calc(-6 / 8 * var(--spinner-animation-duration, 800ms))",
        ":nth-child(4)": "calc(-5 / 8 * var(--spinner-animation-duration, 800ms))",
        ":nth-child(5)": "calc(-4 / 8 * var(--spinner-animation-duration, 800ms))",
        ":nth-child(6)": "calc(-3 / 8 * var(--spinner-animation-duration, 800ms))",
        ":nth-child(7)": "calc(-2 / 8 * var(--spinner-animation-duration, 800ms))",
        ":nth-child(8)": "calc(-1 / 8 * var(--spinner-animation-duration, 800ms))",
    },
    "content": {"::before": "''"},
    "display": {"::before": "block"},
    "borderTopLeftRadius": {"::before": "var(--radius-1)"},
    "borderTopRightRadius": {"::before": "var(--radius-1)"},
    "borderBottomRightRadius": {"::before": "var(--radius-1)"},
    "borderBottomLeftRadius": {"::before": "var(--radius-1)"},
    "backgroundColor": {"::before": "currentColor"},
}


class ButtonState(rx.State):
    """What a button is bound to."""

    busy: bool = False
    off: bool = False


def test_button_plain(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A button is solid, of the second size, and a native button."""
    component = rx.ui.button("Save")
    assert component.render() == {
        "name": '"button"',
        "props": ["className:sx_6fb0976665_c"],
        "children": [{"contents": '"Save"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "var(--space-3)",
            "paddingBottom": "0",
            "paddingLeft": "var(--space-3)",
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
                ":active:not([data-state='open'])": "var(--accent-10)",
                "[data-disabled]": "var(--gray-a3)",
            },
            "backgroundImage": "none",
            "appearance": "none",
            "boxSizing": "border-box",
            "fontSize": "var(--font-size-2)",
            "lineHeight": "var(--line-height-2)",
            "letterSpacing": "var(--letter-spacing-2)",
            "fontWeight": "var(--font-weight-medium)",
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
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
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
            "--rx-icon-opacity": "0.9",
        }
    ]


def test_button_soft_with_a_color_and_a_radius(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A color and a radius are themes on the element, beside its styles."""
    component = rx.ui.button(
        "Save",
        variant="soft",
        size="1",
        color_scheme="ruby",
        radius="full",
        high_contrast=True,
    )
    assert component.render() == {
        "name": '"button"',
        "props": [
            (
                'className:sx_2d7416ba7b_c + " " + reflexUIClasses_e201574881 + " " + '
                "reflexUIClasses_4c7cd6a7ce"
            )
        ],
        "children": [{"contents": '"Save"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "var(--space-2)",
            "paddingBottom": "0",
            "paddingLeft": "var(--space-2)",
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
                ":active:not([data-state='open'])": "var(--accent-a5)",
                "[data-disabled]": "var(--gray-a3)",
            },
            "backgroundImage": "none",
            "appearance": "none",
            "boxSizing": "border-box",
            "fontSize": "var(--font-size-1)",
            "lineHeight": "var(--line-height-1)",
            "letterSpacing": "var(--letter-spacing-1)",
            "fontWeight": "var(--font-weight-medium)",
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
            "--base-button-classic-active-padding-top": "1px",
            "--base-button-height": "var(--space-5)",
            "borderRadius": "max(var(--radius-1), var(--radius-full))",
            "rowGap": "var(--space-1)",
            "columnGap": "var(--space-1)",
            "color": {
                "default": "var(--accent-12)",
                "[data-disabled]": "var(--gray-a8)",
            },
            "outlineWidth": {":focus-visible": "2px"},
            "outlineColor": {":focus-visible": "var(--accent-8)"},
            "outlineOffset": {":focus-visible": "-1px"},
            "--rx-accent-text": "var(--accent-12)",
            "--rx-accent-link": "var(--accent-12)",
            "--rx-accent-link-line": "underline",
            "--rx-accent-link-line-color": "color-mix(in oklab, var(--accent-a6), "
            "var(--gray-a6))",
            "height": "var(--base-button-height)",
            "--rx-icon-opacity": "0.9",
        }
    ]


def test_button_ghost(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A ghost button takes back with margins the padding it adds."""
    component = rx.ui.button("Save", variant="ghost", size="3")
    assert component.render() == {
        "name": '"button"',
        "props": ["className:sx_2251570250_c"],
        "children": [{"contents": '"Save"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "calc(0px - calc(var(--space-1) * 1.5))",
            "marginRight": "calc(0px - var(--space-3))",
            "marginBottom": "calc(0px - calc(var(--space-1) * 1.5))",
            "marginLeft": "calc(0px - var(--space-3))",
            "paddingTop": "calc(var(--space-1) * 1.5)",
            "paddingRight": "var(--space-3)",
            "paddingBottom": "calc(var(--space-1) * 1.5)",
            "paddingLeft": "var(--space-3)",
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
                ":active:not([data-state='open'])": "var(--accent-a4)",
                "[data-disabled]": "transparent",
            },
            "backgroundImage": "none",
            "appearance": "none",
            "boxSizing": "content-box",
            "fontSize": "var(--font-size-3)",
            "lineHeight": "var(--line-height-3)",
            "letterSpacing": "var(--letter-spacing-3)",
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
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
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


def test_button_classic_high_contrast(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The classic variant is drawn by a pseudo-element, with its own states."""
    component = rx.ui.button("Save", variant="classic", high_contrast=True)
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": {
                "default": "0",
                ":active:not([data-state='open'], [data-disabled])": "var(--base-button-classic-active-padding-top)",
            },
            "paddingRight": "var(--space-3)",
            "paddingBottom": "0",
            "paddingLeft": "var(--space-3)",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": {"default": "none", "::after": "solid"},
            "borderRightStyle": {"default": "none", "::after": "solid"},
            "borderBottomStyle": {"default": "none", "::after": "solid"},
            "borderLeftStyle": {"default": "none", "::after": "solid"},
            "backgroundColor": {
                "default": "var(--accent-12)",
                "::after": {
                    "default": "inherit",
                    "@media (hover: hover)": {
                        ":hover:not(:active)": "var(--accent-12)"
                    },
                    ":active:not([data-state='open'], [data-disabled])": "inherit",
                    "[data-disabled]": "var(--gray-a2)",
                },
                ":active:not([data-state='open'], [data-disabled])": "var(--accent-12)",
                "[data-disabled]": "var(--gray-2)",
            },
            "backgroundImage": {
                "default": "linear-gradient(to bottom, transparent 50%, "
                "var(--gray-a4)), linear-gradient(to bottom, "
                "transparent 50%, var(--accent-12) 80%)",
                "::after": {
                    "default": "linear-gradient(var(--black-a3), "
                    "transparent, var(--white-a2))",
                    "@media (hover: hover)": {
                        ":hover:not(:active)": "linear-gradient(var(--black-a5), "
                        "transparent, "
                        "var(--white-a2))"
                    },
                    ":active:not([data-state='open'], [data-disabled])": "linear-gradient(var(--black-a5), "
                    "transparent, "
                    "var(--white-a3))",
                    "[data-disabled]": "linear-gradient(var(--black-a1) "
                    "-20%, transparent, "
                    "var(--white-a1))",
                },
                ":active:not([data-state='open'], [data-disabled])": "linear-gradient(var(--black-a1), "
                "transparent)",
                "[data-disabled]": "none",
            },
            "appearance": "none",
            "boxSizing": {"default": "border-box", "::after": "border-box"},
            "fontSize": "var(--font-size-2)",
            "lineHeight": "var(--line-height-2)",
            "letterSpacing": "var(--letter-spacing-2)",
            "fontWeight": "var(--font-weight-medium)",
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
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
            "boxShadow": {
                "default": "var(--rx-if-light, inset 0 0 0 1px var(--gray-a4), inset 0 "
                "-2px 1px var(--gray-a3)) var(--rx-if-dark, inset 0 0 0 1px "
                "var(--white-a2), inset 0 4px 2px -2px var(--white-a3), "
                "inset 0 1px 1px var(--white-a6), inset 0 -1px 1px "
                "var(--black-a6)), inset 0 0 0 1px var(--accent-12), "
                "var(--rx-if-light, inset 0 4px 2px -2px var(--white-a9), "
                "inset 0 2px 1px -1px var(--white-a9)) var(--rx-if-dark, 0 "
                "0 transparent)",
                "::after": {
                    "default": "inset 0 2px 3px -1px var(--white-a4)",
                    ":active:not([data-state='open'], [data-disabled])": "none",
                    "[data-disabled]": "none",
                },
                ":active:not([data-state='open'], [data-disabled])": "none",
                "[data-disabled]": "var(--rx-if-light, inset 0 0 0 1px var(--gray-a4), "
                "inset 0 -2px 1px var(--gray-a3), inset 0 4px 2px "
                "-2px var(--white-a9), inset 0 2px 1px -1px "
                "var(--white-a9)) var(--rx-if-dark, inset 0 0 0 1px "
                "var(--gray-a5), inset 0 4px 2px -2px "
                "var(--gray-a2), inset 0 1px 1px var(--gray-a5), "
                "inset 0 -1px 1px var(--black-a3), inset 0 0 0 1px "
                "var(--gray-a2))",
            },
            "color": {"default": "var(--gray-1)", "[data-disabled]": "var(--gray-a8)"},
            "position": {"default": "relative", "::after": "absolute"},
            "zIndex": {"default": 0, "::after": -1},
            "content": {"::after": "''"},
            "borderTopLeftRadius": {"::after": "inherit"},
            "borderTopRightRadius": {"::after": "inherit"},
            "borderBottomRightRadius": {"::after": "inherit"},
            "borderBottomLeftRadius": {"::after": "inherit"},
            "pointerEvents": {"::after": "none"},
            "top": {"::after": "0"},
            "right": {"::after": "0"},
            "bottom": {"::after": "0"},
            "left": {"::after": "0"},
            "borderWidth": {
                "::after": "var(--rx-if-light, 2px) var(--rx-if-dark, 1px)"
            },
            "borderTopColor": {"::after": "transparent"},
            "borderRightColor": {"::after": "transparent"},
            "borderBottomColor": {"::after": "transparent"},
            "borderLeftColor": {"::after": "transparent"},
            "backgroundClip": {"::after": "content-box"},
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
            "filter": {
                "[data-disabled]": "none",
                ":active:not([data-state='open'], [data-disabled])": "var(--rx-if-light, "
                "contrast(0.82) "
                "saturate(1.2) "
                "brightness(1.16)) "
                "var(--rx-if-dark, "
                "brightness(0.95) "
                "saturate(1.2))",
                "@media (hover: hover)": {
                    ":hover:not(:active)": "var(--rx-if-light, "
                    "contrast(0.88) "
                    "saturate(1.1) "
                    "brightness(1.1)) "
                    "var(--rx-if-dark, "
                    "contrast(0.88) "
                    "saturate(1.3) "
                    "brightness(1.14))"
                },
            },
            "height": "var(--base-button-height)",
            "--rx-icon-opacity": "0.9",
        }
    ]


def test_button_responsive_size(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A size per breakpoint changes what the size sets, at the breakpoints of Radix Themes."""
    component = rx.ui.button(
        "Save", variant="outline", size=rx.breakpoints(initial="1", md="3")
    )
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": {
                "default": "var(--space-2)",
                "@media (min-width: 1024px)": "var(--space-4)",
            },
            "paddingBottom": "0",
            "paddingLeft": {
                "default": "var(--space-2)",
                "@media (min-width: 1024px)": "var(--space-4)",
            },
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
                "@media (hover: hover)": {":hover:not(:active)": "var(--accent-a2)"},
                ":active:not([data-state='open'])": "var(--accent-a3)",
                "[data-disabled]": "transparent",
            },
            "backgroundImage": "none",
            "appearance": "none",
            "boxSizing": "border-box",
            "fontSize": {
                "default": "var(--font-size-1)",
                "@media (min-width: 1024px)": "var(--font-size-3)",
            },
            "lineHeight": {
                "default": "var(--line-height-1)",
                "@media (min-width: 1024px)": "var(--line-height-3)",
            },
            "letterSpacing": {
                "default": "var(--letter-spacing-1)",
                "@media (min-width: 1024px)": "var(--letter-spacing-3)",
            },
            "fontWeight": "var(--font-weight-medium)",
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
            "--base-button-classic-active-padding-top": {
                "default": "1px",
                "@media (min-width: 1024px)": "2px",
            },
            "--base-button-height": {
                "default": "var(--space-5)",
                "@media (min-width: 1024px)": "var(--space-7)",
            },
            "borderRadius": {
                "default": "max(var(--radius-1), var(--radius-full))",
                "@media (min-width: 1024px)": "max(var(--radius-3), "
                "var(--radius-full))",
            },
            "rowGap": {
                "default": "var(--space-1)",
                "@media (min-width: 1024px)": "var(--space-3)",
            },
            "columnGap": {
                "default": "var(--space-1)",
                "@media (min-width: 1024px)": "var(--space-3)",
            },
            "boxShadow": {
                "default": "inset 0 0 0 1px var(--accent-a8)",
                "[data-disabled]": "inset 0 0 0 1px var(--gray-a7)",
            },
            "color": {
                "default": "var(--accent-a11)",
                "[data-disabled]": "var(--gray-a8)",
            },
            "outlineWidth": {":focus-visible": "2px"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "outlineOffset": {":focus-visible": "-1px"},
            "height": "var(--base-button-height)",
            "--rx-icon-opacity": "0.9",
        }
    ]


def test_button_disabled(
    ui_plugin: UIPlugin,
):
    """A disabled button says so in data-disabled, which its styles select on."""
    component = rx.ui.button("Save", disabled=True, type="submit")
    assert component.render() == {
        "name": '"button"',
        "props": [
            "className:sx_6fb0976665_c",
            '"data-disabled":true',
            "disabled:true",
            'type:"submit"',
        ],
        "children": [{"contents": '"Save"'}],
    }


def test_button_loading(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A loading button is disabled, and shows a spinner over children that keep their place."""
    component = rx.ui.button("Save", loading=True, size="4")
    assert component.render() == {
        "name": '"button"',
        "props": ["className:sx_e8602a468e_c", '"data-disabled":true', "disabled:true"],
        "children": [
            {
                "name": '"span"',
                "props": ['"aria-hidden":true', "className:sx_33a975bab1_c"],
                "children": [{"contents": '"Save"'}],
            },
            {
                "name": '"span"',
                "props": ["className:sx_0daea2e46b_c"],
                "children": [{"contents": '"Save"'}],
            },
            {
                "name": '"span"',
                "props": ["className:sx_67bf81be86_c"],
                "children": [
                    {
                        "name": '"span"',
                        "props": ["className:sx_12ba415941_c"],
                        "children": [
                            {
                                "name": '"span"',
                                "props": ["className:sx_32f6bd5200_c"],
                                "children": [],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_32f6bd5200_c"],
                                "children": [],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_32f6bd5200_c"],
                                "children": [],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_32f6bd5200_c"],
                                "children": [],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_32f6bd5200_c"],
                                "children": [],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_32f6bd5200_c"],
                                "children": [],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_32f6bd5200_c"],
                                "children": [],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_32f6bd5200_c"],
                                "children": [],
                            },
                        ],
                    }
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "var(--space-5)",
            "paddingBottom": "0",
            "paddingLeft": "var(--space-5)",
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
                ":active:not([data-state='open'])": "var(--accent-10)",
                "[data-disabled]": "var(--gray-a3)",
            },
            "backgroundImage": "none",
            "appearance": "none",
            "boxSizing": "border-box",
            "fontSize": "var(--font-size-4)",
            "lineHeight": "var(--line-height-4)",
            "letterSpacing": "var(--letter-spacing-4)",
            "fontWeight": "var(--font-weight-medium)",
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
            "--base-button-height": "var(--space-8)",
            "borderRadius": "max(var(--radius-4), var(--radius-full))",
            "rowGap": "var(--space-3)",
            "columnGap": "var(--space-3)",
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
            "position": "relative",
            "height": "var(--base-button-height)",
            "--rx-icon-opacity": "0.9",
        },
        {"display": "contents", "visibility": "hidden"},
        {
            "position": "absolute",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "width": "1px",
            "height": "1px",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "marginTop": "-1px",
            "marginRight": "-1px",
            "marginBottom": "-1px",
            "marginLeft": "-1px",
            "overflowX": "hidden",
            "overflowY": "hidden",
            "clip": "rect(0, 0, 0, 0)",
            "whiteSpace": "nowrap",
            "wordWrap": "normal",
        },
        {
            "boxSizing": "border-box",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "position": "absolute",
            "top": "0",
            "right": "0",
            "bottom": "0",
            "left": "0",
        },
        {
            "display": "block",
            "position": "relative",
            "opacity": "var(--spinner-opacity, 0.65)",
            "width": "calc(1.25 * var(--space-4))",
            "height": "calc(1.25 * var(--space-4))",
        },
        LEAF,
        LEAF,
        LEAF,
        LEAF,
        LEAF,
        LEAF,
        LEAF,
        LEAF,
    ]


def test_button_bound_to_state(
    ui_plugin: UIPlugin,
):
    """Loading and disabled bound to state choose the children and the attributes in the browser."""
    component = rx.ui.button("Save", loading=ButtonState.busy, disabled=ButtonState.off)
    assert component.render() == {
        "name": '"button"',
        "props": [
            (
                'className:sx_aec9f4943f_c + " " + '
                "(sx_aec9f4943f_0[reflex___state____state__tests___units___reflex_components_ui___components___test_button____button_state.busy_rx_state_] "
                '?? "")'
            ),
            (
                '"data-disabled":((reflex___state____state__tests___units___reflex_components_ui___components___test_button____button_state.off_rx_state_ '
                "|| "
                "reflex___state____state__tests___units___reflex_components_ui___components___test_button____button_state.busy_rx_state_) "
                "|| undefined)"
            ),
            (
                "disabled:(reflex___state____state__tests___units___reflex_components_ui___components___test_button____button_state.off_rx_state_ "
                "|| "
                "reflex___state____state__tests___units___reflex_components_ui___components___test_button____button_state.busy_rx_state_)"
            ),
        ],
        "children": [
            {
                "name": "Fragment",
                "props": [],
                "children": [
                    {
                        "cond_state": "reflex___state____state__tests___units___reflex_components_ui___components___test_button____button_state.busy_rx_state_",
                        "true_value": {
                            "name": "Fragment",
                            "props": [],
                            "children": [
                                {
                                    "name": '"span"',
                                    "props": [
                                        '"aria-hidden":true',
                                        "className:sx_33a975bab1_c",
                                    ],
                                    "children": [{"contents": '"Save"'}],
                                },
                                {
                                    "name": '"span"',
                                    "props": ["className:sx_0daea2e46b_c"],
                                    "children": [{"contents": '"Save"'}],
                                },
                                {
                                    "name": '"span"',
                                    "props": ["className:sx_67bf81be86_c"],
                                    "children": [
                                        {
                                            "name": '"span"',
                                            "props": ["className:sx_fe93a2d910_c"],
                                            "children": [
                                                {
                                                    "name": '"span"',
                                                    "props": [
                                                        "className:sx_32f6bd5200_c"
                                                    ],
                                                    "children": [],
                                                },
                                                {
                                                    "name": '"span"',
                                                    "props": [
                                                        "className:sx_32f6bd5200_c"
                                                    ],
                                                    "children": [],
                                                },
                                                {
                                                    "name": '"span"',
                                                    "props": [
                                                        "className:sx_32f6bd5200_c"
                                                    ],
                                                    "children": [],
                                                },
                                                {
                                                    "name": '"span"',
                                                    "props": [
                                                        "className:sx_32f6bd5200_c"
                                                    ],
                                                    "children": [],
                                                },
                                                {
                                                    "name": '"span"',
                                                    "props": [
                                                        "className:sx_32f6bd5200_c"
                                                    ],
                                                    "children": [],
                                                },
                                                {
                                                    "name": '"span"',
                                                    "props": [
                                                        "className:sx_32f6bd5200_c"
                                                    ],
                                                    "children": [],
                                                },
                                                {
                                                    "name": '"span"',
                                                    "props": [
                                                        "className:sx_32f6bd5200_c"
                                                    ],
                                                    "children": [],
                                                },
                                                {
                                                    "name": '"span"',
                                                    "props": [
                                                        "className:sx_32f6bd5200_c"
                                                    ],
                                                    "children": [],
                                                },
                                            ],
                                        }
                                    ],
                                },
                            ],
                        },
                        "false_value": {
                            "name": "Fragment",
                            "props": [],
                            "children": [{"contents": '"Save"'}],
                        },
                    }
                ],
            }
        ],
    }


def test_button_as_child(
    ui_plugin: UIPlugin,
):
    """With as_child the only child is the element, with the styles of the button."""
    component = rx.ui.button(
        rx.el.a("Docs", href="/docs"), as_child=True, disabled=True
    )
    assert component.render() == {
        "name": "ReactRouterLink",
        "props": [
            "className:sx_6fb0976665_c",
            '"data-disabled":true',
            "disabled:true",
            'to:"/docs"',
        ],
        "children": [{"contents": '"Docs"'}],
    }


def test_button_as_child_literal_var(ui_plugin: UIPlugin):
    """A literal Var for as_child is read as its value, loading or not."""
    child = rx.el.a("Docs", href="/docs")
    expected = rx.ui.button(child, as_child=True, loading=False).render()
    assert expected["name"] == "ReactRouterLink"
    assert (
        rx.ui.button(child, as_child=rx.Var.create(True), loading=False).render()
        == expected
    )
    assert (
        rx.ui.button("Save", as_child=rx.Var.create(False), loading=False).render()
        == rx.ui.button("Save", loading=False).render()
    )


@pytest.mark.parametrize(
    ("props", "error", "message"),
    [
        (
            {"variant": "sold"},
            StyleError,
            (
                'rx.ui.button: unknown variant "sold". Did you mean "solid"? The values '
                'are "classic", "solid", "soft", "surface", "outline", "ghost".'
            ),
        ),
        (
            {"size": "5"},
            StyleError,
            'rx.ui.button: unknown size "5". The values are "1", "2", "3", "4".',
        ),
        (
            {"radius": "round"},
            ThemeError,
            (
                'rx.ui.button: unknown radius "round". The values are "none", "small", '
                '"medium", "large", "full".'
            ),
        ),
        (
            {"color_scheme": "rubi"},
            ThemeError,
            (
                'rx.ui.button: unknown color_scheme "rubi". Did you mean "ruby"? The '
                'values are "tomato", "red", "ruby", "crimson", "pink", "plum", '
                '"purple", "violet", "iris", "indigo", "blue", "cyan", "teal", "jade", '
                '"green", "grass", "brown", "orange", "sky", "mint", "lime", "yellow", '
                '"amber", "gold", "bronze", "gray".'
            ),
        ),
    ],
)
def test_button_rejects_a_value_a_prop_does_not_take(
    props: dict[str, str], error: type[Exception], message: str
):
    """The error names the component, the prop and the values it takes."""
    with pytest.raises(error) as raised:
        rx.ui.button("Save", **props)  # pyright: ignore[reportArgumentType]
    assert str(raised.value) == message


def test_button_rendered_from_state_cannot_carry_a_radius(ui_plugin: UIPlugin):
    """A theme on an element needs the build, as its styles do."""
    token = _RENDERING_DYNAMIC_COMPONENT.set(True)
    try:
        with pytest.raises(StyleError) as raised:
            rx.ui.button("Save", radius="full").render()
    finally:
        _RENDERING_DYNAMIC_COMPONENT.reset(token)
    assert str(raised.value) == (
        "rx.ui.button: radius cannot be applied to a component rendered from "
        "state: its code is evaluated in the browser and never reaches the StyleX "
        "compiler. Render the component in a page and show it with rx.cond."
    )
