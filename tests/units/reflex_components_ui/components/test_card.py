"""Tests for reflex_components_ui.components.card."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


def test_card_plain(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A card is a surface of the first size, drawn by two pseudo-elements."""
    component = rx.ui.card("Invoice")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_8966fad991_c"],
        "children": [{"contents": '"Invoice"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": {":is(a, button)": "none"},
            "borderRightStyle": {":is(a, button)": "none"},
            "borderBottomStyle": {":is(a, button)": "none"},
            "borderLeftStyle": {":is(a, button)": "none"},
            "backgroundColor": {
                "default": "transparent",
                "::before": "var(--card-background-color)",
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    ":focus-visible:active:not([data-state='open'])": "linear-gradient(var(--focus-a2), "
                    "var(--focus-a2))",
                    "@media (pointer: coarse)": {
                        ":is(:any-link, button, label):active:not(:focus-visible, [data-state='open'])": "linear-gradient(var(--gray-a4), "
                        "var(--gray-a4))"
                    },
                },
            },
            "appearance": "none",
            "color": "inherit",
            "fontSize": "inherit",
            "fontWeight": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "textDecorationLine": "none",
            "textTransform": "inherit",
            "textIndent": "initial",
            "textShadow": "inherit",
            "wordSpacing": "inherit",
            "cursor": {
                ":where(button):not(:disabled, [data-disabled])": "var(--cursor-button)",
                ":any-link:not([data-disabled])": "var(--cursor-link)",
                ":is(:disabled, [data-disabled])": "var(--cursor-disabled)",
            },
            "outlineStyle": {
                "default": "none",
                ":focus-visible": "solid",
                "::after": {":focus-visible": "solid"},
            },
            "WebkitTapHighlightColor": "transparent",
            "display": "block",
            "position": {
                "default": "relative",
                "::before": "absolute",
                "::after": "absolute",
            },
            "overflowX": "hidden",
            "overflowY": "hidden",
            "borderRadius": {
                "default": "var(--card-border-radius)",
                "::before": "calc(var(--card-border-radius) - "
                "var(--card-border-width))",
                "::after": "calc(var(--card-border-radius) - var(--card-border-width))",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "padding": "var(--card-padding)",
            "boxSizing": {
                "default": "border-box",
                "::before": "border-box",
                "::after": "border-box",
            },
            "contain": "paint",
            "--inset-border-width": "var(--card-border-width)",
            "--inset-border-radius": "var(--card-border-radius)",
            "--inset-padding-top": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-right": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-bottom": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-left": "calc(var(--card-padding) - var(--card-border-width))",
            "content": {"::before": "''", "::after": "''"},
            "pointerEvents": {"::before": "none", "::after": "none"},
            "transitionProperty": {"::before": "inherit", "::after": "inherit"},
            "transitionDuration": {"::before": "inherit", "::after": "inherit"},
            "transitionTimingFunction": {"::before": "inherit", "::after": "inherit"},
            "transitionDelay": {"::before": "inherit", "::after": "inherit"},
            "inset": {
                "::before": "var(--card-border-width)",
                "::after": "var(--card-border-width)",
            },
            "zIndex": {"::before": -1},
            "outlineWidth": {
                "::after": {":focus-visible": "2px"},
                ":focus-visible": "2px",
            },
            "outlineColor": {
                "::after": {":focus-visible": "var(--focus-8)"},
                ":focus-visible": "var(--focus-8)",
            },
            "outlineOffset": {":focus-visible": "-1px"},
            "--card-padding": "var(--space-3)",
            "--card-border-radius": "var(--radius-4)",
            "--card-border-width": "1px",
            "--card-background-color": "var(--color-panel)",
            "backdropFilter": {"::before": "var(--backdrop-filter-panel)"},
            "boxShadow": {
                "::after": {
                    "default": "0 0 0 1px color-mix(in oklab, var(--gray-a5), "
                    "var(--gray-5) 25%)",
                    "@media (hover: hover)": {
                        ":is(:any-link, button, label):hover:not(:active)": "0 "
                        "0 "
                        "0 "
                        "1px "
                        "color-mix(in "
                        "oklab, "
                        "var(--gray-a7), "
                        "var(--gray-7) "
                        "25%)"
                    },
                    ":is(:any-link, button, label)[data-state='open']": "0 0 0 "
                    "1px "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a7), "
                    "var(--gray-7) "
                    "25%)",
                    ":is(:any-link, button, label):active:not([data-state='open'])": "0 "
                    "0 "
                    "0 "
                    "1px "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a6), "
                    "var(--gray-6) "
                    "25%)",
                }
            },
        }
    ]


def test_card_classic(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The classic card repeats its shadow on itself, one pixel smaller."""
    component = rx.ui.card("Invoice", variant="classic", size="3")
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": {":is(a, button)": "none"},
            "borderRightStyle": {":is(a, button)": "none"},
            "borderBottomStyle": {":is(a, button)": "none"},
            "borderLeftStyle": {":is(a, button)": "none"},
            "backgroundColor": {
                "default": "transparent",
                "::before": "var(--card-background-color)",
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    ":focus-visible:active:not([data-state='open'])": "linear-gradient(var(--focus-a2), "
                    "var(--focus-a2))",
                    "@media (pointer: coarse)": {
                        ":is(:any-link, button, label):active:not(:focus-visible, [data-state='open'])": "linear-gradient(var(--gray-a4), "
                        "var(--gray-a4))"
                    },
                },
            },
            "appearance": "none",
            "color": "inherit",
            "fontSize": "inherit",
            "fontWeight": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "textDecorationLine": "none",
            "textTransform": "inherit",
            "textIndent": "initial",
            "textShadow": "inherit",
            "wordSpacing": "inherit",
            "cursor": {
                ":where(button):not(:disabled, [data-disabled])": "var(--cursor-button)",
                ":any-link:not([data-disabled])": "var(--cursor-link)",
                ":is(:disabled, [data-disabled])": "var(--cursor-disabled)",
            },
            "outlineStyle": {
                "default": "none",
                ":focus-visible": "solid",
                "::after": {":focus-visible": "solid"},
            },
            "WebkitTapHighlightColor": "transparent",
            "display": "block",
            "position": {
                "default": "relative",
                "::before": "absolute",
                "::after": "absolute",
            },
            "overflowX": "hidden",
            "overflowY": "hidden",
            "borderRadius": {
                "default": "var(--card-border-radius)",
                "::before": "calc(var(--card-border-radius) - "
                "var(--card-border-width))",
                "::after": "calc(var(--card-border-radius) - var(--card-border-width))",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "padding": "var(--card-padding)",
            "boxSizing": {
                "default": "border-box",
                "::before": "border-box",
                "::after": "border-box",
            },
            "contain": "paint",
            "--inset-border-width": "var(--card-border-width)",
            "--inset-border-radius": "var(--card-border-radius)",
            "--inset-padding-top": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-right": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-bottom": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-left": "calc(var(--card-padding) - var(--card-border-width))",
            "content": {"::before": "''", "::after": "''"},
            "pointerEvents": {"::before": "none", "::after": "none"},
            "transitionProperty": {
                "default": "box-shadow",
                "::before": "inherit",
                "::after": "inherit",
            },
            "transitionDuration": {
                "default": "120ms",
                "@media (hover: hover)": {
                    ":is(:any-link, button, label):hover:not(:active)": "40ms"
                },
                ":is(:any-link, button, label)[data-state='open']": "40ms",
                ":is(:any-link, button, label):active:not([data-state='open'])": "40ms",
                "::before": "inherit",
                "::after": "inherit",
            },
            "transitionTimingFunction": {"::before": "inherit", "::after": "inherit"},
            "transitionDelay": {"::before": "inherit", "::after": "inherit"},
            "inset": {
                "::before": "var(--card-border-width)",
                "::after": "var(--card-border-width)",
            },
            "zIndex": {"::before": -1},
            "outlineWidth": {
                "::after": {":focus-visible": "2px"},
                ":focus-visible": "2px",
            },
            "outlineColor": {
                "::after": {":focus-visible": "var(--focus-8)"},
                ":focus-visible": "var(--focus-8)",
            },
            "outlineOffset": {":focus-visible": "-1px"},
            "--card-padding": "var(--space-5)",
            "--card-border-radius": "var(--radius-5)",
            "--card-border-width": "1px",
            "--card-background-color": "var(--color-panel)",
            "boxShadow": {
                "default": "var(--rx-if-light, 0 0 0 0 color-mix(in oklab, "
                "var(--gray-a3), var(--gray-3) 25%), 0 0 0 0 "
                "var(--color-transparent), 0 0 0 0 var(--black-a1), 0 1px "
                "1px -1px var(--gray-a2), 0 2px 1px -2px var(--black-a1), 0 "
                "1px 3px -1px var(--black-a1)) var(--rx-if-dark, 0 0 0 0 "
                "color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 "
                "0 0 0 var(--color-transparent), 0 0 0 0 var(--black-a3), 0 "
                "1px 1px -1px var(--black-a6), 0 2px 1px -2px "
                "var(--black-a6), 0 1px 3px -1px var(--black-a5))",
                "@media (hover: hover)": {
                    ":is(:any-link, button, label):hover:not(:active)": "var(--rx-if-light, "
                    "0 "
                    "0 "
                    "0 "
                    "0 "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a4), "
                    "var(--gray-4) "
                    "25%), "
                    "0 "
                    "1px "
                    "1px "
                    "0 "
                    "var(--black-a1), "
                    "0 "
                    "2px "
                    "1px "
                    "-2px "
                    "var(--gray-a3), "
                    "0 "
                    "2px "
                    "3px "
                    "-3px "
                    "var(--black-a1), "
                    "0 "
                    "3px "
                    "12px "
                    "-5px "
                    "var(--gray-a3), "
                    "0 "
                    "4px "
                    "16px "
                    "-9px "
                    "var(--black-a1)) "
                    "var(--rx-if-dark, "
                    "0 "
                    "0 "
                    "0 "
                    "0 "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a6), "
                    "var(--gray-6) "
                    "25%), "
                    "0 "
                    "0 "
                    "1px "
                    "0 "
                    "var(--gray-a4), "
                    "0 "
                    "0 "
                    "1px "
                    "-2px "
                    "var(--gray-a4), "
                    "0 "
                    "0 "
                    "3px "
                    "-3px "
                    "var(--gray-a3), "
                    "0 "
                    "0 "
                    "12px "
                    "-3px "
                    "var(--gray-a3), "
                    "0 "
                    "0 "
                    "16px "
                    "-9px "
                    "var(--gray-a7))"
                },
                ":is(:any-link, button, label)[data-state='open']": "var(--rx-if-light, "
                "0 0 0 0 "
                "color-mix(in "
                "oklab, "
                "var(--gray-a4), "
                "var(--gray-4) "
                "25%), 0 1px 1px 0 "
                "var(--black-a1), "
                "0 2px 1px -2px "
                "var(--gray-a3), 0 "
                "2px 3px -3px "
                "var(--black-a1), "
                "0 3px 12px -5px "
                "var(--gray-a3), 0 "
                "4px 16px -9px "
                "var(--black-a1)) "
                "var(--rx-if-dark, "
                "0 0 0 0 "
                "color-mix(in "
                "oklab, "
                "var(--gray-a6), "
                "var(--gray-6) "
                "25%), 0 0 1px 0 "
                "var(--gray-a4), 0 "
                "0 1px -2px "
                "var(--gray-a4), 0 "
                "0 3px -3px "
                "var(--gray-a3), 0 "
                "0 12px -3px "
                "var(--gray-a3), 0 "
                "0 16px -9px "
                "var(--gray-a7))",
                ":is(:any-link, button, label):active:not([data-state='open'])": "var(--rx-if-light, "
                "0 0 "
                "0 0 "
                "color-mix(in "
                "oklab, "
                "var(--gray-a3), "
                "var(--gray-3) "
                "25%), "
                "0 0 "
                "0 0 "
                "var(--color-transparent), "
                "0 0 "
                "0 0 "
                "var(--black-a1), "
                "0 "
                "1px "
                "1px "
                "-1px "
                "var(--gray-a4), "
                "0 "
                "2px "
                "1px "
                "-2px "
                "var(--black-a1), "
                "0 "
                "1px "
                "3px "
                "-1px "
                "var(--black-a1)) "
                "var(--rx-if-dark, "
                "0 0 "
                "0 0 "
                "color-mix(in "
                "oklab, "
                "var(--gray-a6), "
                "var(--gray-6) "
                "25%), "
                "0 0 "
                "0 0 "
                "var(--color-transparent), "
                "0 0 "
                "0 0 "
                "var(--black-a3), "
                "0 "
                "1px "
                "1px "
                "-1px "
                "var(--black-a6), "
                "0 "
                "2px "
                "1px "
                "-2px "
                "var(--black-a6), "
                "0 "
                "1px "
                "3px "
                "-1px "
                "var(--black-a5))",
                "::after": {
                    "default": "var(--rx-if-light, 0 0 0 1px color-mix(in "
                    "oklab, var(--gray-a3), var(--gray-3) 25%), 0 0 "
                    "0 1px var(--color-transparent), 0 0 0 0.5px "
                    "var(--black-a1), 0 1px 1px 0 var(--gray-a2), 0 "
                    "2px 1px -1px var(--black-a1), 0 1px 3px 0 "
                    "var(--black-a1)) var(--rx-if-dark, 0 0 0 1px "
                    "color-mix(in oklab, var(--gray-a6), "
                    "var(--gray-6) 25%), 0 0 0 1px "
                    "var(--color-transparent), 0 0 0 0.5px "
                    "var(--black-a3), 0 1px 1px 0 var(--black-a6), "
                    "0 2px 1px -1px var(--black-a6), 0 1px 3px 0 "
                    "var(--black-a5))",
                    "@media (hover: hover)": {
                        ":is(:any-link, button, label):hover:not(:active)": "var(--rx-if-light, "
                        "0 "
                        "0 "
                        "0 "
                        "1px "
                        "color-mix(in "
                        "oklab, "
                        "var(--gray-a4), "
                        "var(--gray-4) "
                        "25%), "
                        "0 "
                        "1px "
                        "1px "
                        "1px "
                        "var(--black-a1), "
                        "0 "
                        "2px "
                        "1px "
                        "-1px "
                        "var(--gray-a3), "
                        "0 "
                        "2px "
                        "3px "
                        "-2px "
                        "var(--black-a1), "
                        "0 "
                        "3px "
                        "12px "
                        "-4px "
                        "var(--gray-a3), "
                        "0 "
                        "4px "
                        "16px "
                        "-8px "
                        "var(--black-a1)) "
                        "var(--rx-if-dark, "
                        "0 "
                        "0 "
                        "0 "
                        "1px "
                        "color-mix(in "
                        "oklab, "
                        "var(--gray-a6), "
                        "var(--gray-6) "
                        "25%), "
                        "0 "
                        "0 "
                        "1px "
                        "1px "
                        "var(--gray-a4), "
                        "0 "
                        "0 "
                        "1px "
                        "-1px "
                        "var(--gray-a4), "
                        "0 "
                        "0 "
                        "3px "
                        "-2px "
                        "var(--gray-a3), "
                        "0 "
                        "0 "
                        "12px "
                        "-2px "
                        "var(--gray-a3), "
                        "0 "
                        "0 "
                        "16px "
                        "-8px "
                        "var(--gray-a7))"
                    },
                    ":is(:any-link, button, label)[data-state='open']": "var(--rx-if-light, "
                    "0 0 0 "
                    "1px "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a4), "
                    "var(--gray-4) "
                    "25%), "
                    "0 1px "
                    "1px "
                    "1px "
                    "var(--black-a1), "
                    "0 2px "
                    "1px "
                    "-1px "
                    "var(--gray-a3), "
                    "0 2px "
                    "3px "
                    "-2px "
                    "var(--black-a1), "
                    "0 3px "
                    "12px "
                    "-4px "
                    "var(--gray-a3), "
                    "0 4px "
                    "16px "
                    "-8px "
                    "var(--black-a1)) "
                    "var(--rx-if-dark, "
                    "0 0 0 "
                    "1px "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a6), "
                    "var(--gray-6) "
                    "25%), "
                    "0 0 "
                    "1px "
                    "1px "
                    "var(--gray-a4), "
                    "0 0 "
                    "1px "
                    "-1px "
                    "var(--gray-a4), "
                    "0 0 "
                    "3px "
                    "-2px "
                    "var(--gray-a3), "
                    "0 0 "
                    "12px "
                    "-2px "
                    "var(--gray-a3), "
                    "0 0 "
                    "16px "
                    "-8px "
                    "var(--gray-a7))",
                    ":is(:any-link, button, label):active:not([data-state='open'])": "var(--rx-if-light, "
                    "0 "
                    "0 "
                    "0 "
                    "1px "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a3), "
                    "var(--gray-3) "
                    "25%), "
                    "0 "
                    "0 "
                    "0 "
                    "1px "
                    "var(--color-transparent), "
                    "0 "
                    "0 "
                    "0 "
                    "0.5px "
                    "var(--black-a1), "
                    "0 "
                    "1px "
                    "1px "
                    "0 "
                    "var(--gray-a4), "
                    "0 "
                    "2px "
                    "1px "
                    "-1px "
                    "var(--black-a1), "
                    "0 "
                    "1px "
                    "3px "
                    "0 "
                    "var(--black-a1)) "
                    "var(--rx-if-dark, "
                    "0 "
                    "0 "
                    "0 "
                    "1px "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a6), "
                    "var(--gray-6) "
                    "25%), "
                    "0 "
                    "0 "
                    "0 "
                    "1px "
                    "var(--color-transparent), "
                    "0 "
                    "0 "
                    "0 "
                    "0.5px "
                    "var(--black-a3), "
                    "0 "
                    "1px "
                    "1px "
                    "0 "
                    "var(--black-a6), "
                    "0 "
                    "2px "
                    "1px "
                    "-1px "
                    "var(--black-a6), "
                    "0 "
                    "1px "
                    "3px "
                    "0 "
                    "var(--black-a5))",
                },
            },
            "backdropFilter": {"::before": "var(--backdrop-filter-panel)"},
        }
    ]


def test_card_ghost_responsive(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A ghost card takes back its padding, at each size of a breakpoint."""
    component = rx.ui.card(
        "Invoice", variant="ghost", size=rx.breakpoints(initial="1", md="4")
    )
    assert declared_styles(component) == [
        {
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": {":is(a, button)": "none"},
            "borderRightStyle": {":is(a, button)": "none"},
            "borderBottomStyle": {":is(a, button)": "none"},
            "borderLeftStyle": {":is(a, button)": "none"},
            "backgroundColor": {
                "default": "transparent",
                "@media (hover: hover)": {
                    ":is(:any-link, button, label):hover:not(:active, :focus-visible)": "var(--gray-a3)",
                    ":is(:any-link, button, label):hover:focus-visible": "var(--focus-a2)",
                },
                ":is(:any-link, button, label)[data-state='open']:not(:focus-visible)": "var(--gray-a3)",
                ":is(:any-link, button, label):active:not([data-state='open'], :focus-visible)": "var(--gray-a4)",
                ":is(:any-link, button, label):focus-visible:is(:active, [data-state='open'])": "var(--focus-a2)",
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    ":focus-visible:active:not([data-state='open'])": "linear-gradient(var(--focus-a2), "
                    "var(--focus-a2))",
                    "@media (pointer: coarse)": {
                        ":is(:any-link, button, label):active:not(:focus-visible, [data-state='open'])": "linear-gradient(var(--gray-a4), "
                        "var(--gray-a4))"
                    },
                },
            },
            "appearance": "none",
            "color": "inherit",
            "fontSize": "inherit",
            "fontWeight": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "textDecorationLine": "none",
            "textTransform": "inherit",
            "textIndent": "initial",
            "textShadow": "inherit",
            "wordSpacing": "inherit",
            "cursor": {
                ":where(button):not(:disabled, [data-disabled])": "var(--cursor-button)",
                ":any-link:not([data-disabled])": "var(--cursor-link)",
                ":is(:disabled, [data-disabled])": "var(--cursor-disabled)",
            },
            "outlineStyle": {
                "default": "none",
                ":focus-visible": "solid",
                "::after": {":focus-visible": "solid"},
            },
            "WebkitTapHighlightColor": "transparent",
            "display": "block",
            "position": {
                "default": "relative",
                "::before": "absolute",
                "::after": "absolute",
            },
            "overflowX": "hidden",
            "overflowY": "hidden",
            "borderRadius": {
                "default": "var(--card-border-radius)",
                "::before": "calc(var(--card-border-radius) - "
                "var(--card-border-width))",
                "::after": "calc(var(--card-border-radius) - var(--card-border-width))",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "padding": "var(--card-padding)",
            "boxSizing": {
                "default": "border-box",
                "::before": "border-box",
                "::after": "border-box",
            },
            "contain": "paint",
            "--inset-border-width": "var(--card-border-width)",
            "--inset-border-radius": "var(--card-border-radius)",
            "--inset-padding-top": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-right": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-bottom": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-left": "calc(var(--card-padding) - var(--card-border-width))",
            "content": {"::before": "''", "::after": "''"},
            "pointerEvents": {"::before": "none", "::after": "none"},
            "transitionProperty": {"::before": "inherit", "::after": "inherit"},
            "transitionDuration": {"::before": "inherit", "::after": "inherit"},
            "transitionTimingFunction": {"::before": "inherit", "::after": "inherit"},
            "transitionDelay": {"::before": "inherit", "::after": "inherit"},
            "inset": {
                "::before": "var(--card-border-width)",
                "::after": "var(--card-border-width)",
            },
            "zIndex": {"::before": -1},
            "outlineWidth": {
                "::after": {":focus-visible": "2px"},
                ":focus-visible": "2px",
            },
            "outlineColor": {
                "::after": {":focus-visible": "var(--focus-8)"},
                ":focus-visible": "var(--focus-8)",
            },
            "outlineOffset": {":focus-visible": "-1px"},
            "--card-padding": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "var(--space-6)",
            },
            "--card-border-radius": {
                "default": "var(--radius-4)",
                "@media (min-width: 1024px)": "var(--radius-5)",
            },
            "--card-border-width": "0px",
            "margin": "calc(0px - var(--card-padding))",
        }
    ]


def test_card_as_child(
    ui_plugin: UIPlugin,
):
    """A card rendered as a link is the link, with the styles of the card."""
    component = rx.ui.card(rx.el.a("Invoice", href="/invoice"), as_child=True)
    assert component.render() == {
        "name": "ReactRouterLink",
        "props": ["className:sx_8966fad991_c", 'to:"/invoice"'],
        "children": [{"contents": '"Invoice"'}],
    }


def test_card_keeps_its_surface_under_a_background(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A style of the element leaves the pseudo-elements what the card gives them."""
    component = rx.ui.card("Invoice", background_color="red")
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": {":is(a, button)": "none"},
            "borderRightStyle": {":is(a, button)": "none"},
            "borderBottomStyle": {":is(a, button)": "none"},
            "borderLeftStyle": {":is(a, button)": "none"},
            "backgroundColor": {
                "default": "red",
                "::before": "var(--card-background-color)",
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    ":focus-visible:active:not([data-state='open'])": "linear-gradient(var(--focus-a2), "
                    "var(--focus-a2))",
                    "@media (pointer: coarse)": {
                        ":is(:any-link, button, label):active:not(:focus-visible, [data-state='open'])": "linear-gradient(var(--gray-a4), "
                        "var(--gray-a4))"
                    },
                },
            },
            "appearance": "none",
            "color": "inherit",
            "fontSize": "inherit",
            "fontWeight": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "textDecorationLine": "none",
            "textTransform": "inherit",
            "textIndent": "initial",
            "textShadow": "inherit",
            "wordSpacing": "inherit",
            "cursor": {
                ":where(button):not(:disabled, [data-disabled])": "var(--cursor-button)",
                ":any-link:not([data-disabled])": "var(--cursor-link)",
                ":is(:disabled, [data-disabled])": "var(--cursor-disabled)",
            },
            "outlineStyle": {
                "default": "none",
                ":focus-visible": "solid",
                "::after": {":focus-visible": "solid"},
            },
            "WebkitTapHighlightColor": "transparent",
            "display": "block",
            "position": {
                "default": "relative",
                "::before": "absolute",
                "::after": "absolute",
            },
            "overflowX": "hidden",
            "overflowY": "hidden",
            "borderRadius": {
                "default": "var(--card-border-radius)",
                "::before": "calc(var(--card-border-radius) - "
                "var(--card-border-width))",
                "::after": "calc(var(--card-border-radius) - var(--card-border-width))",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "padding": "var(--card-padding)",
            "boxSizing": {
                "default": "border-box",
                "::before": "border-box",
                "::after": "border-box",
            },
            "contain": "paint",
            "--inset-border-width": "var(--card-border-width)",
            "--inset-border-radius": "var(--card-border-radius)",
            "--inset-padding-top": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-right": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-bottom": "calc(var(--card-padding) - var(--card-border-width))",
            "--inset-padding-left": "calc(var(--card-padding) - var(--card-border-width))",
            "content": {"::before": "''", "::after": "''"},
            "pointerEvents": {"::before": "none", "::after": "none"},
            "transitionProperty": {"::before": "inherit", "::after": "inherit"},
            "transitionDuration": {"::before": "inherit", "::after": "inherit"},
            "transitionTimingFunction": {"::before": "inherit", "::after": "inherit"},
            "transitionDelay": {"::before": "inherit", "::after": "inherit"},
            "inset": {
                "::before": "var(--card-border-width)",
                "::after": "var(--card-border-width)",
            },
            "zIndex": {"::before": -1},
            "outlineWidth": {
                "::after": {":focus-visible": "2px"},
                ":focus-visible": "2px",
            },
            "outlineColor": {
                "::after": {":focus-visible": "var(--focus-8)"},
                ":focus-visible": "var(--focus-8)",
            },
            "outlineOffset": {":focus-visible": "-1px"},
            "--card-padding": "var(--space-3)",
            "--card-border-radius": "var(--radius-4)",
            "--card-border-width": "1px",
            "--card-background-color": "var(--color-panel)",
            "backdropFilter": {"::before": "var(--backdrop-filter-panel)"},
            "boxShadow": {
                "::after": {
                    "default": "0 0 0 1px color-mix(in oklab, var(--gray-a5), "
                    "var(--gray-5) 25%)",
                    "@media (hover: hover)": {
                        ":is(:any-link, button, label):hover:not(:active)": "0 "
                        "0 "
                        "0 "
                        "1px "
                        "color-mix(in "
                        "oklab, "
                        "var(--gray-a7), "
                        "var(--gray-7) "
                        "25%)"
                    },
                    ":is(:any-link, button, label)[data-state='open']": "0 0 0 "
                    "1px "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a7), "
                    "var(--gray-7) "
                    "25%)",
                    ":is(:any-link, button, label):active:not([data-state='open'])": "0 "
                    "0 "
                    "0 "
                    "1px "
                    "color-mix(in "
                    "oklab, "
                    "var(--gray-a6), "
                    "var(--gray-6) "
                    "25%)",
                }
            },
        }
    ]


def test_card_rejects_a_value_a_prop_does_not_take():
    """The error names the component, the prop and the values it takes."""
    with pytest.raises(StyleError) as raised:
        rx.ui.card("Invoice", variant="solid")  # pyright: ignore[reportArgumentType]
    assert str(raised.value) == (
        'rx.ui.card: unknown variant "solid". The values are "surface", '
        '"classic", "ghost".'
    )
