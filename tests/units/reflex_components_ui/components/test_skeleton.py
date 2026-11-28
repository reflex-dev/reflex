"""Tests for reflex_components_ui.components.skeleton."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import Keyframes

import reflex as rx


class SkeletonState(rx.State):
    """What a skeleton is bound to."""

    loading: bool = True


def test_skeleton_around_text(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """Around text a skeleton is a span, hidden from the keyboard and from a reader."""
    component = rx.ui.skeleton(
        "1,204 euros", width=rx.breakpoints(initial="60px", md="160px")
    )
    assert component.render() == {
        "name": '"span"',
        "props": [
            '"aria-hidden":true',
            "className:sx_dc6750d851_c",
            '"data-rx-skeleton":""',
            "inert:true",
            "tabIndex:-1",
        ],
        "children": [{"contents": '"1,204 euros"'}],
    }
    assert declared_styles(component) == [
        {
            "animationName": Keyframes(
                (
                    '{"from": {"backgroundColor": "var(--gray-a3)"}, "to": {"backgroundColor": "var(--gray-a4)"}}',
                ),
                ("$/reflex-ui/tokens/gray.stylex.js",),
            ),
            "animationDuration": "1000ms !important",
            "animationTimingFunction": "ease !important",
            "animationDelay": "0s !important",
            "animationIterationCount": "infinite !important",
            "animationDirection": "alternate-reverse !important",
            "animationFillMode": "none !important",
            "animationPlayState": "running !important",
            "backgroundImage": "none !important",
            "backgroundClip": "border-box !important",
            "borderStyle": "none !important",
            "borderWidth": "medium !important",
            "borderColor": "currentcolor !important",
            "boxShadow": "none !important",
            "boxDecorationBreak": "clone !important",
            "color": "transparent !important",
            "outlineStyle": "none !important",
            "outlineWidth": "medium !important",
            "outlineColor": "currentcolor !important",
            "pointerEvents": "none !important",
            "userSelect": "none !important",
            "cursor": "default !important",
            "visibility": {
                "::before": "hidden !important",
                "::after": "hidden !important",
            },
            "display": {":empty": "block"},
            "height": {":empty": "var(--space-3)"},
            "borderTopLeftRadius": "var(--radius-1)",
            "borderTopRightRadius": "var(--radius-1)",
            "borderBottomRightRadius": "var(--radius-1)",
            "borderBottomLeftRadius": "var(--radius-1)",
            "lineHeight": 0,
            "fontFamily": "Arial, sans-serif !important",
            "width": {"default": "60px", "@media (min-width: 1024px)": "160px"},
        }
    ]


def test_skeleton_alone(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A skeleton that holds nothing is a line of its own."""
    component = rx.ui.skeleton(height="40px")
    assert component.render() == {
        "name": '"span"',
        "props": [
            '"aria-hidden":true',
            "className:sx_77a15491e1_c",
            '"data-rx-skeleton":""',
            "inert:true",
            "tabIndex:-1",
        ],
        "children": [],
    }
    assert declared_styles(component) == [
        {
            "animationName": Keyframes(
                (
                    '{"from": {"backgroundColor": "var(--gray-a3)"}, "to": {"backgroundColor": "var(--gray-a4)"}}',
                ),
                ("$/reflex-ui/tokens/gray.stylex.js",),
            ),
            "animationDuration": "1000ms !important",
            "animationTimingFunction": "ease !important",
            "animationDelay": "0s !important",
            "animationIterationCount": "infinite !important",
            "animationDirection": "alternate-reverse !important",
            "animationFillMode": "none !important",
            "animationPlayState": "running !important",
            "backgroundImage": "none !important",
            "backgroundClip": "border-box !important",
            "borderStyle": "none !important",
            "borderWidth": "medium !important",
            "borderColor": "currentcolor !important",
            "boxShadow": "none !important",
            "boxDecorationBreak": "clone !important",
            "color": "transparent !important",
            "outlineStyle": "none !important",
            "outlineWidth": "medium !important",
            "outlineColor": "currentcolor !important",
            "pointerEvents": "none !important",
            "userSelect": "none !important",
            "cursor": "default !important",
            "visibility": {
                "::before": "hidden !important",
                "::after": "hidden !important",
            },
            "display": {":empty": "block"},
            "height": "40px",
            "borderTopLeftRadius": "var(--radius-1)",
            "borderTopRightRadius": "var(--radius-1)",
            "borderBottomRightRadius": "var(--radius-1)",
            "borderBottomLeftRadius": "var(--radius-1)",
            "lineHeight": 0,
            "fontFamily": "Arial, sans-serif !important",
        }
    ]


def test_skeleton_as_its_child(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """Around one element a skeleton is that element, which keeps its styles and its corners."""
    component = rx.ui.skeleton(rx.ui.button("Save", id="save"), width="120px")
    assert component.render() == {
        "name": '"button"',
        "props": [
            '"aria-hidden":true',
            'className:(sx_f2580dfc68_c) + " " + sx_596747f37d_c',
            '"data-rx-skeleton":""',
            'id:"save"',
            "inert:true",
            "ref:ref_save",
            "tabIndex:-1",
        ],
        "children": [{"contents": '"Save"'}],
    }
    assert declared_styles(component) == [
        {
            "animationName": Keyframes(
                (
                    '{"from": {"backgroundColor": "var(--gray-a3)"}, "to": {"backgroundColor": "var(--gray-a4)"}}',
                ),
                ("$/reflex-ui/tokens/gray.stylex.js",),
            ),
            "animationDuration": "1000ms !important",
            "animationTimingFunction": "ease !important",
            "animationDelay": "0s !important",
            "animationIterationCount": "infinite !important",
            "animationDirection": "alternate-reverse !important",
            "animationFillMode": "none !important",
            "animationPlayState": "running !important",
            "backgroundImage": "none !important",
            "backgroundClip": "border-box !important",
            "borderStyle": "none !important",
            "borderWidth": "medium !important",
            "borderColor": "currentcolor !important",
            "boxShadow": "none !important",
            "boxDecorationBreak": "clone !important",
            "color": "transparent !important",
            "outlineStyle": "none !important",
            "outlineWidth": "medium !important",
            "outlineColor": "currentcolor !important",
            "pointerEvents": "none !important",
            "userSelect": "none !important",
            "cursor": "default !important",
            "visibility": {
                "::before": "hidden !important",
                "::after": "hidden !important",
            },
            "display": {":empty": "block"},
            "height": {":empty": "var(--space-3)"},
            "width": "120px !important",
        },
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
                "[data-state='open']": "var(--accent-10)",
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
        },
    ]


def test_skeleton_not_loading(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A skeleton that is not loading is its children, untouched."""
    component = rx.ui.skeleton(rx.ui.button("Save"), loading=False)
    assert component.render() == {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "name": '"button"',
                "props": ["className:sx_f2580dfc68_c"],
                "children": [{"contents": '"Save"'}],
            }
        ],
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
                "[data-state='open']": "var(--accent-10)",
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


def test_skeleton_bound_to_state(
    ui_plugin: UIPlugin,
):
    """Loading bound to state chooses between the skeleton and the child in the browser."""
    component = rx.ui.skeleton(rx.el.div("Report"), loading=SkeletonState.loading)
    assert component.render() == {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "cond_state": "reflex___state____state__tests___units___reflex_components_ui___components___test_skeleton____skeleton_state.loading_rx_state_",
                "true_value": {
                    "name": "Fragment",
                    "props": [],
                    "children": [
                        {
                            "name": '"div"',
                            "props": [
                                '"aria-hidden":true',
                                "className:sx_89c14fd899_c",
                                '"data-rx-skeleton":""',
                                "inert:true",
                                "tabIndex:-1",
                            ],
                            "children": [{"contents": '"Report"'}],
                        }
                    ],
                },
                "false_value": {
                    "name": "Fragment",
                    "props": [],
                    "children": [
                        {
                            "name": "Fragment",
                            "props": [],
                            "children": [
                                {
                                    "name": '"div"',
                                    "props": [],
                                    "children": [{"contents": '"Report"'}],
                                }
                            ],
                        }
                    ],
                },
            }
        ],
    }
