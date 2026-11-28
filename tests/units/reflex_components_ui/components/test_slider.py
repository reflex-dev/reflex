"""Tests for reflex_components_ui.components.slider."""

import re
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


class SliderState(rx.State):
    """What a slider is bound to."""

    span: list[float] = [20, 60]
    low: int = 10

    @rx.event
    def set_span(self, span: list[float]):
        """Follow the slider.

        Args:
            span: Its values.
        """
        self.span = span


def test_slider(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A slider is a track, its filled part and a native range input for its thumb, which has the id, the name and the label of the slider."""
    component = rx.ui.slider(
        default_value=30,
        id="volume",
        name="volume",
        min=0,
        max=200,
        step=5,
        aria_label="Volume",
        width="50%",
        margin="1px",
    )
    assert component.render() == {
        "name": '"span"',
        "props": [
            "className:sx_2e50c10c69_c",
            '"data-orientation":"horizontal"',
            "onInputCapture:slide",
        ],
        "children": [
            {
                "name": '"span"',
                "props": ["className:sx_9a52612950_c"],
                "children": [
                    {
                        "name": '"span"',
                        "props": ["className:sx_3462dcdb83_c"],
                        "children": [],
                    }
                ],
            },
            {
                "name": '"input"',
                "props": [
                    '"aria-label":"Volume"',
                    "className:sx_2ed6fd010a_c",
                    "defaultValue:30",
                    'id:"volume"',
                    "max:200",
                    "min:0",
                    'name:"volume"',
                    "step:5",
                    'type:"range"',
                ],
                "children": [],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "--slider-thumb-size": "calc(var(--slider-track-size) + var(--space-1))",
            "position": "relative",
            "display": "flex",
            "alignItems": "center",
            "flexGrow": 1,
            "borderRadius": "max(calc(var(--radius-factor) * var(--slider-track-size) / 3), calc(var(--radius-factor) * var(--radius-thumb)))",
            "userSelect": "none",
            "touchAction": "none",
            "cursor": {":has(:disabled)": "var(--cursor-disabled)"},
            "mixBlendMode": {
                ":has(:disabled)": "var(--rx-if-light, multiply) var(--rx-if-dark, screen)"
            },
            "--slider-track-size": "var(--space-2)",
            "width": "50%",
            "height": "var(--slider-track-size)",
            "--rx-slider-start": "0%",
            "--rx-slider-end": "15%",
            "marginTop": "1px",
            "marginRight": "1px",
            "marginBottom": "1px",
            "marginLeft": "1px",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "position": "relative",
            "flexGrow": 1,
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "height": "var(--slider-track-size)",
            "backgroundColor": "var(--gray-a3)",
            "boxShadow": "inset 0 0 0 1px var(--gray-a5)",
        },
        {
            "position": "absolute",
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "height": "100%",
            "left": "var(--rx-slider-start)",
            "right": "calc(100% - var(--rx-slider-end))",
            "backgroundColor": "var(--accent-track)",
            "backgroundImage": "none",
            "boxShadow": "inset 0 0 0 1px var(--gray-a5)",
        },
        {
            "appearance": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "position": "absolute",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderRightWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderBottomWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderLeftWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderTopStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderRightStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderBottomStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderLeftStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "backgroundColor": {
                "default": "transparent",
                "::-webkit-slider-runnable-track": "transparent",
                "::-webkit-slider-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
                "::-moz-range-track": "transparent",
                "::-moz-range-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
            },
            "outlineStyle": "none",
            "cursor": {
                "default": "inherit",
                "::-webkit-slider-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
                "::-moz-range-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
            },
            "width": {
                "default": "calc(100% + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "height": {
                "default": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-runnable-track": "100%",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-track": "100%",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "left": "calc(var(--slider-track-size) * -0.25)",
            "top": "calc(50% - calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5) / 2)",
            "boxSizing": {
                "::-webkit-slider-thumb": "border-box",
                "::-moz-range-thumb": "border-box",
            },
            "pointerEvents": {
                "::-webkit-slider-thumb": "auto",
                "::-moz-range-thumb": "auto",
            },
            "borderRadius": {
                "::-webkit-slider-thumb": "max(var(--radius-1), var(--radius-thumb))",
                "::-moz-range-thumb": "max(var(--radius-1), var(--radius-thumb))",
            },
            "boxShadow": {
                "::-webkit-slider-thumb": {
                    "default": "0 0 0 1px var(--black-a4)",
                    ":focus-visible": "0 0 0 1px var(--black-a4), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-6)",
                },
                "::-moz-range-thumb": {
                    "default": "0 0 0 1px var(--black-a4)",
                    ":focus-visible": "0 0 0 1px var(--black-a4), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-6)",
                },
            },
        },
    ]


def test_slider_with_several_thumbs(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A slider with several values has a thumb for each, named as Radix names them in a group with the name of the slider, and its script moves the nearest."""
    component = rx.ui.slider(
        default_value=[20, 60, 90],
        name="span",
        aria_label="Span",
        disabled=True,
        size="3",
        variant="classic",
        high_contrast=True,
        color_scheme="ruby",
        radius="small",
        orientation="vertical",
        as_child=True,
    )
    assert component.render() == {
        "name": '"span"',
        "props": [
            '"aria-label":"Span"',
            'className:sx_2a31e8da62_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_6d1e87c3d8',
            '"data-orientation":"vertical"',
            "onInputCapture:slide",
            "onMouseDown:press",
            'role:"group"',
        ],
        "children": [
            {
                "name": '"span"',
                "props": ["className:sx_c5bed6bb3f_c"],
                "children": [
                    {
                        "name": '"span"',
                        "props": ["className:sx_fff88394c2_c"],
                        "children": [],
                    }
                ],
            },
            {
                "name": '"input"',
                "props": [
                    '"aria-label":"Value 1 of 3"',
                    "className:sx_1c26558511_c",
                    "defaultValue:20",
                    "disabled:true",
                    'name:"span[]"',
                    'type:"range"',
                ],
                "children": [],
            },
            {
                "name": '"input"',
                "props": [
                    '"aria-label":"Value 2 of 3"',
                    "className:sx_1c26558511_c",
                    "defaultValue:60",
                    "disabled:true",
                    'name:"span[]"',
                    'type:"range"',
                ],
                "children": [],
            },
            {
                "name": '"input"',
                "props": [
                    '"aria-label":"Value 3 of 3"',
                    "className:sx_1c26558511_c",
                    "defaultValue:90",
                    "disabled:true",
                    'name:"span[]"',
                    'type:"range"',
                ],
                "children": [],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "--slider-thumb-size": "calc(var(--slider-track-size) + var(--space-1))",
            "position": "relative",
            "display": "flex",
            "alignItems": "center",
            "flexGrow": 1,
            "borderRadius": "max(calc(var(--radius-factor) * var(--slider-track-size) / 3), calc(var(--radius-factor) * var(--radius-thumb)))",
            "userSelect": "none",
            "touchAction": "none",
            "cursor": {":has(:disabled)": "var(--cursor-disabled)"},
            "mixBlendMode": {
                ":has(:disabled)": "var(--rx-if-light, multiply) var(--rx-if-dark, screen)"
            },
            "--slider-track-size": "calc(var(--space-2) * 1.25)",
            "height": "stretch",
            "flexDirection": "column",
            "width": "100%",
            "--rx-slider-start": "20%",
            "--rx-slider-end": "90%",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "position": {"default": "relative", "::before": "absolute"},
            "flexGrow": 1,
            "borderTopLeftRadius": {"default": "inherit", "::before": "inherit"},
            "borderTopRightRadius": {"default": "inherit", "::before": "inherit"},
            "borderBottomRightRadius": {"default": "inherit", "::before": "inherit"},
            "borderBottomLeftRadius": {"default": "inherit", "::before": "inherit"},
            "width": "var(--slider-track-size)",
            "backgroundColor": "var(--gray-a3)",
            "content": {"::before": "''"},
            "top": {"::before": "0"},
            "right": {"::before": "0"},
            "bottom": {"::before": "0"},
            "left": {"::before": "0"},
            "boxShadow": {"::before": "var(--shadow-1)"},
            "opacity": {"::before": 0.5},
        },
        {
            "position": "absolute",
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "width": "100%",
            "bottom": "var(--rx-slider-start)",
            "top": "calc(100% - var(--rx-slider-end))",
            "backgroundColor": "transparent",
            "backgroundImage": "none",
            "boxShadow": "none",
        },
        {
            "appearance": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "position": "absolute",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderRightWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderBottomWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderLeftWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderTopStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderRightStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderBottomStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderLeftStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "backgroundColor": {
                "default": "transparent",
                "::-webkit-slider-runnable-track": "transparent",
                "::-webkit-slider-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
                "::-moz-range-track": "transparent",
                "::-moz-range-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
            },
            "outlineStyle": "none",
            "cursor": {
                "default": "inherit",
                "::-webkit-slider-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
                "::-moz-range-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
            },
            "height": {
                "default": "calc(100% + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-runnable-track": "100%",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-track": "100%",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "width": {
                "default": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "top": "calc(var(--slider-track-size) * -0.25)",
            "left": "calc(50% - calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5) / 2)",
            "writingMode": "vertical-lr",
            "direction": "rtl",
            "boxSizing": {
                "::-webkit-slider-thumb": "border-box",
                "::-moz-range-thumb": "border-box",
            },
            "pointerEvents": {
                "default": "none",
                "::-webkit-slider-thumb": "auto",
                "::-moz-range-thumb": "auto",
            },
            "borderRadius": {
                "::-webkit-slider-thumb": "max(var(--radius-1), var(--radius-thumb))",
                "::-moz-range-thumb": "max(var(--radius-1), var(--radius-thumb))",
            },
            "boxShadow": {
                "::-webkit-slider-thumb": {
                    "default": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1)",
                    ":focus-visible": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-6)",
                },
                "::-moz-range-thumb": {
                    "default": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1)",
                    ":focus-visible": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-6)",
                },
            },
        },
        {
            "appearance": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "position": "absolute",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderRightWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderBottomWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderLeftWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderTopStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderRightStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderBottomStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderLeftStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "backgroundColor": {
                "default": "transparent",
                "::-webkit-slider-runnable-track": "transparent",
                "::-webkit-slider-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
                "::-moz-range-track": "transparent",
                "::-moz-range-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
            },
            "outlineStyle": "none",
            "cursor": {
                "default": "inherit",
                "::-webkit-slider-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
                "::-moz-range-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
            },
            "height": {
                "default": "calc(100% + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-runnable-track": "100%",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-track": "100%",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "width": {
                "default": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "top": "calc(var(--slider-track-size) * -0.25)",
            "left": "calc(50% - calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5) / 2)",
            "writingMode": "vertical-lr",
            "direction": "rtl",
            "boxSizing": {
                "::-webkit-slider-thumb": "border-box",
                "::-moz-range-thumb": "border-box",
            },
            "pointerEvents": {
                "default": "none",
                "::-webkit-slider-thumb": "auto",
                "::-moz-range-thumb": "auto",
            },
            "borderRadius": {
                "::-webkit-slider-thumb": "max(var(--radius-1), var(--radius-thumb))",
                "::-moz-range-thumb": "max(var(--radius-1), var(--radius-thumb))",
            },
            "boxShadow": {
                "::-webkit-slider-thumb": {
                    "default": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1)",
                    ":focus-visible": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-6)",
                },
                "::-moz-range-thumb": {
                    "default": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1)",
                    ":focus-visible": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-6)",
                },
            },
        },
        {
            "appearance": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "position": "absolute",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderRightWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderBottomWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderLeftWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderTopStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderRightStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderBottomStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderLeftStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "backgroundColor": {
                "default": "transparent",
                "::-webkit-slider-runnable-track": "transparent",
                "::-webkit-slider-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
                "::-moz-range-track": "transparent",
                "::-moz-range-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
            },
            "outlineStyle": "none",
            "cursor": {
                "default": "inherit",
                "::-webkit-slider-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
                "::-moz-range-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
            },
            "height": {
                "default": "calc(100% + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-runnable-track": "100%",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-track": "100%",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "width": {
                "default": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "top": "calc(var(--slider-track-size) * -0.25)",
            "left": "calc(50% - calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5) / 2)",
            "writingMode": "vertical-lr",
            "direction": "rtl",
            "boxSizing": {
                "::-webkit-slider-thumb": "border-box",
                "::-moz-range-thumb": "border-box",
            },
            "pointerEvents": {
                "default": "none",
                "::-webkit-slider-thumb": "auto",
                "::-moz-range-thumb": "auto",
            },
            "borderRadius": {
                "::-webkit-slider-thumb": "max(var(--radius-1), var(--radius-thumb))",
                "::-moz-range-thumb": "max(var(--radius-1), var(--radius-thumb))",
            },
            "boxShadow": {
                "::-webkit-slider-thumb": {
                    "default": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1)",
                    ":focus-visible": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-6)",
                },
                "::-moz-range-thumb": {
                    "default": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1)",
                    ":focus-visible": "0 0 0 1px var(--black-a3), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-6)",
                },
            },
        },
    ]


def test_slider_soft(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The soft variant, and the default value of a slider."""
    component = rx.ui.slider(variant="soft")
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "--slider-thumb-size": "calc(var(--slider-track-size) + var(--space-1))",
            "position": "relative",
            "display": "flex",
            "alignItems": "center",
            "flexGrow": 1,
            "borderRadius": "max(calc(var(--radius-factor) * var(--slider-track-size) / 3), calc(var(--radius-factor) * var(--radius-thumb)))",
            "userSelect": "none",
            "touchAction": "none",
            "cursor": {":has(:disabled)": "var(--cursor-disabled)"},
            "mixBlendMode": {
                ":has(:disabled)": "var(--rx-if-light, multiply) var(--rx-if-dark, screen)"
            },
            "--slider-track-size": "var(--space-2)",
            "width": "100%",
            "height": "var(--slider-track-size)",
            "--rx-slider-start": "0%",
            "--rx-slider-end": "50%",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "position": "relative",
            "flexGrow": 1,
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "height": "var(--slider-track-size)",
            "backgroundColor": "var(--gray-a4)",
            "backgroundImage": "linear-gradient(var(--white-a1), var(--white-a1))",
        },
        {
            "position": "absolute",
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "height": "100%",
            "left": "var(--rx-slider-start)",
            "right": "calc(100% - var(--rx-slider-end))",
            "backgroundColor": "var(--accent-6)",
            "backgroundImage": "linear-gradient(var(--accent-a5), var(--accent-a5)), none",
        },
        {
            "appearance": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "position": "absolute",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderRightWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderBottomWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderLeftWidth": {
                "default": "0",
                "::-webkit-slider-thumb": "0",
                "::-moz-range-thumb": "0",
            },
            "borderTopStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderRightStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderBottomStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "borderLeftStyle": {
                "default": "none",
                "::-webkit-slider-thumb": "none",
                "::-moz-range-thumb": "none",
            },
            "backgroundColor": {
                "default": "transparent",
                "::-webkit-slider-runnable-track": "transparent",
                "::-webkit-slider-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
                "::-moz-range-track": "transparent",
                "::-moz-range-thumb": {
                    "default": "white",
                    ":disabled": "var(--gray-1)",
                },
            },
            "outlineStyle": "none",
            "cursor": {
                "default": "inherit",
                "::-webkit-slider-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
                "::-moz-range-thumb": {
                    "default": "var(--cursor-slider-thumb)",
                    ":active": "var(--cursor-slider-thumb-active)",
                    ":disabled": "var(--cursor-disabled)",
                },
            },
            "width": {
                "default": "calc(100% + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "height": {
                "default": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-webkit-slider-runnable-track": "100%",
                "::-webkit-slider-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
                "::-moz-range-track": "100%",
                "::-moz-range-thumb": "calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5)",
            },
            "left": "calc(var(--slider-track-size) * -0.25)",
            "top": "calc(50% - calc(var(--slider-thumb-size) + var(--slider-track-size) * 0.5) / 2)",
            "boxSizing": {
                "::-webkit-slider-thumb": "border-box",
                "::-moz-range-thumb": "border-box",
            },
            "pointerEvents": {
                "::-webkit-slider-thumb": "auto",
                "::-moz-range-thumb": "auto",
            },
            "borderRadius": {
                "::-webkit-slider-thumb": "max(var(--radius-1), var(--radius-thumb))",
                "::-moz-range-thumb": "max(var(--radius-1), var(--radius-thumb))",
            },
            "boxShadow": {
                "::-webkit-slider-thumb": {
                    "default": "0 0 0 1px var(--black-a3), 0 0 0 1px var(--gray-a2), 0 0 0 1px var(--accent-a2), 0 1px 2px var(--gray-a4), 0 1px 3px -0.5px var(--gray-a3)",
                    ":focus-visible": "0 0 0 1px var(--black-a3), 0 0 0 1px var(--gray-a2), 0 0 0 1px var(--accent-a2), 0 1px 2px var(--gray-a4), 0 1px 3px -0.5px var(--gray-a3), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-5)",
                },
                "::-moz-range-thumb": {
                    "default": "0 0 0 1px var(--black-a3), 0 0 0 1px var(--gray-a2), 0 0 0 1px var(--accent-a2), 0 1px 2px var(--gray-a4), 0 1px 3px -0.5px var(--gray-a3)",
                    ":focus-visible": "0 0 0 1px var(--black-a3), 0 0 0 1px var(--gray-a2), 0 0 0 1px var(--accent-a2), 0 1px 2px var(--gray-a4), 0 1px 3px -0.5px var(--gray-a3), 0 0 0 3px var(--accent-3), 0 0 0 5px var(--focus-8)",
                    ":disabled": "0 0 0 1px var(--gray-5)",
                },
            },
        },
    ]


def test_slider_unknown_radius(ui_plugin: UIPlugin):
    """A radius a slider does not have is an error that lists the ones it has."""
    with pytest.raises(StyleError) as error:
        rx.ui.slider(radius="large")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == 'rx.ui.slider: unknown radius "large". The values are "none", "small", "full".'
    )


def test_slider_bound_to_state(ui_plugin: UIPlugin):
    """A slider bound to a list has a thumb for each value, counted in the browser, and hands the values over."""
    slider = rx.ui.slider(
        value=SliderState.span,
        min=SliderState.low,
        on_change=SliderState.set_span,
        on_value_commit=SliderState.set_span,
    )
    state = (
        "tests___units___reflex_components_ui___components___test_slider"
        "____slider_state"
    )
    span = f"reflex___state____state__{state}.span_rx_state_"
    low = f"reflex___state____state__{state}.low_rx_state_"
    values = (
        'Array.from(_e.currentTarget.querySelectorAll("input"), '
        "(input) => input.valueAsNumber)"
    )
    handler = (
        '((_e) => (addEvents([(ReflexEvent("reflex___state____state.'
        f'{state}.set_span", ({{ ["span"] : {values} }}), ({{  }})))], [_e], '
        "({  }))))"
    )
    keys = (
        '["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", '
        '"PageUp", "PageDown"]'
    )
    assert slider.render()["props"] == [
        "className:sx_d6dc3ba3e7_c",
        '"data-orientation":"horizontal"',
        f"onChange:{handler}",
        "onInputCapture:slide",
        f"onKeyUp:((event) => {{ if ({keys}.includes(event.key)) ({handler})(event); }})",
        "onMouseDown:press",
        f"onPointerUp:{handler}",
        (
            f'style:({{ "--v0": ((((({span}?.at?.(0)) - ({low})) / ((100) - ({low})) '
            f'* 100) + "%")) ?? "initial", "--v1": ((((({span}?.at?.(-1)) - ({low})) '
            f'/ ((100) - ({low})) * 100) + "%")) ?? "initial" }})'
        ),
    ]
    thumb = slider.children[1].children[0]
    # Named after the bytecode of the function that renders a thumb, which
    # differs from one Python version to the next.
    index = slider.children[1].render()["index_var_name"]
    assert re.fullmatch(r"index_[0-9a-f]{32}", index)
    assert thumb.render()["props"] == [
        "className:sx_04c810abee_c",
        f"key:{index}",
        f"min:{low}",
        'type:"range"',
        'value:(isNotNullOrUndefined(item_rx_state_) ? item_rx_state_ : "")',
    ]


def test_slider_script(ui_plugin: UIPlugin):
    """The script of a slider follows its thumbs, and moves the nearest of several."""
    script = "$/reflex-ui/behaviors/slider.js"
    assert rx.ui.slider()._get_all_imports()[script] == [ImportVar(tag="slide")]
    assert rx.ui.slider(default_value=[1, 2])._get_all_imports()[script] == [
        ImportVar(tag="slide"),
        ImportVar(tag="press"),
    ]
