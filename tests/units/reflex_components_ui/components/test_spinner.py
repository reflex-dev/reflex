"""Tests for reflex_components_ui.components.spinner."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import Keyframes

import reflex as rx

# What each leaf of a spinner declares.
LEAF: dict[str, Any] = {
    "position": "absolute",
    "top": "0",
    "left": "calc(50% - 12.5% / 2)",
    "width": {"default": "12.5%", "::before": "100%"},
    "height": {"default": "100%", "::before": "30%"},
    "animationName": Keyframes('{"from": {"opacity": 1}, "to": {"opacity": 0.25}}', ()),
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


class SpinnerState(rx.State):
    """What a spinner is bound to."""

    busy: bool = True


def test_spinner_alone(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A spinner is a span of eight leaves, each turned and delayed by its place."""
    component = rx.ui.spinner(id="wait")
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_fe93a2d910_c", 'id:"wait"', "ref:ref_wait"],
        "children": [
            {"name": '"span"', "props": ["className:sx_32f6bd5200_c"], "children": []},
            {"name": '"span"', "props": ["className:sx_32f6bd5200_c"], "children": []},
            {"name": '"span"', "props": ["className:sx_32f6bd5200_c"], "children": []},
            {"name": '"span"', "props": ["className:sx_32f6bd5200_c"], "children": []},
            {"name": '"span"', "props": ["className:sx_32f6bd5200_c"], "children": []},
            {"name": '"span"', "props": ["className:sx_32f6bd5200_c"], "children": []},
            {"name": '"span"', "props": ["className:sx_32f6bd5200_c"], "children": []},
            {"name": '"span"', "props": ["className:sx_32f6bd5200_c"], "children": []},
        ],
    }
    assert declared_styles(component) == [
        {
            "display": "block",
            "position": "relative",
            "opacity": "var(--spinner-opacity, 0.65)",
            "width": "var(--space-4)",
            "height": "var(--space-4)",
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


def test_spinner_size(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The size of a spinner may change at a breakpoint."""
    component = rx.ui.spinner(size=rx.breakpoints(initial="1", md="3"))
    assert declared_styles(component) == [
        {
            "display": "block",
            "position": "relative",
            "opacity": "var(--spinner-opacity, 0.65)",
            "width": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "calc(1.25 * var(--space-4))",
            },
            "height": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "calc(1.25 * var(--space-4))",
            },
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


def test_spinner_over_children(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """Around children, the spinner is centered over their place."""
    component = rx.ui.spinner("Report", size="3")
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_826ff773c9_c"],
        "children": [
            {
                "name": '"span"',
                "props": ['"aria-hidden":true', "className:sx_33a975bab1_c"],
                "children": [{"contents": '"Report"'}],
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
            "boxSizing": "border-box",
            "display": "flex",
            "position": "relative",
            "alignItems": "center",
            "justifyContent": "center",
        },
        {"display": "contents", "visibility": "hidden"},
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


def test_spinner_not_loading(
    ui_plugin: UIPlugin,
):
    """A spinner that is not loading is its children."""
    component = rx.ui.spinner("Report", loading=False)
    assert component.render() == {
        "name": "Fragment",
        "props": [],
        "children": [{"contents": '"Report"'}],
    }


def test_spinner_bound_to_state(
    ui_plugin: UIPlugin,
):
    """Loading bound to state chooses between the spinner and the children in the browser."""
    component = rx.ui.spinner("Report", loading=SpinnerState.busy)
    assert component.render() == {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "cond_state": "reflex___state____state__tests___units___reflex_components_ui___components___test_spinner____spinner_state.busy_rx_state_",
                "true_value": {
                    "name": "Fragment",
                    "props": [],
                    "children": [
                        {
                            "name": '"span"',
                            "props": ["className:sx_826ff773c9_c"],
                            "children": [
                                {
                                    "name": '"span"',
                                    "props": [
                                        '"aria-hidden":true',
                                        "className:sx_33a975bab1_c",
                                    ],
                                    "children": [{"contents": '"Report"'}],
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
                            "children": [{"contents": '"Report"'}],
                        }
                    ],
                },
            }
        ],
    }
