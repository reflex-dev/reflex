"""Tests for reflex_components_ui.components.segmented_control."""

import itertools
import re
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.components import _group
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


@pytest.fixture(autouse=True)
def names(monkeypatch: pytest.MonkeyPatch):
    """Number the controls of each test from one: the name groups their items."""
    monkeypatch.setattr(_group, "_names", itertools.count(1))


class SegmentedState(rx.State):
    """What a segmented control is bound to."""

    view: str = "b"
    views: list[str] = ["a", "b"]

    @rx.event
    def set_view(self, view: str):
        """Follow the control.

        Args:
            view: The value of the chosen item.
        """
        self.view = view


def test_segmented_control(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """An item is a label around a native radio button and its text, twice; the control counts its items for what marks the chosen one."""
    component = rx.ui.segmented_control.root(
        rx.ui.segmented_control.item("One", value="1", id="one"),
        rx.ui.segmented_control.item("Two", value="2", margin="1px"),
        default_value="2",
        size="3",
        variant="classic",
        radius="full",
        color_scheme="ruby",
        type="multiple",
        id="views",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            'className:sx_66f6ec5e0a_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_4c7cd6a7ce',
            'id:"views"',
            "onKeyDown:rovingKeyDown",
            "ref:ref_views",
            'role:"radiogroup"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_7f4c9c997f_c", '"data-rx-segmented-item":""'],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_8e51139181_c",
                            'form:""',
                            'id:"one"',
                            'name:"rx-segmented-1"',
                            "ref:ref_one",
                            'type:"radio"',
                            'value:"1"',
                        ],
                        "children": [],
                    },
                    {
                        "name": '"span"',
                        "props": ["className:sx_f0662e97c2_c"],
                        "children": [],
                    },
                    {
                        "name": '"span"',
                        "props": ["className:sx_f91740a5b0_c"],
                        "children": [
                            {
                                "name": '"span"',
                                "props": ["className:sx_48fb0dc076_c"],
                                "children": [{"contents": '"One"'}],
                            },
                            {
                                "name": '"span"',
                                "props": [
                                    '"aria-hidden":true',
                                    "className:sx_d60de3577e_c",
                                ],
                                "children": [{"contents": '"One"'}],
                            },
                        ],
                    },
                ],
            },
            {
                "name": '"label"',
                "props": ["className:sx_c43e9e9803_c", '"data-rx-segmented-item":""'],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_8e51139181_c",
                            "defaultChecked:true",
                            'form:""',
                            'name:"rx-segmented-1"',
                            'type:"radio"',
                            'value:"2"',
                        ],
                        "children": [],
                    },
                    {
                        "name": '"span"',
                        "props": ["className:sx_f0662e97c2_c"],
                        "children": [],
                    },
                    {
                        "name": '"span"',
                        "props": ["className:sx_f91740a5b0_c"],
                        "children": [
                            {
                                "name": '"span"',
                                "props": ["className:sx_48fb0dc076_c"],
                                "children": [{"contents": '"Two"'}],
                            },
                            {
                                "name": '"span"',
                                "props": [
                                    '"aria-hidden":true',
                                    "className:sx_d60de3577e_c",
                                ],
                                "children": [{"contents": '"Two"'}],
                            },
                        ],
                    },
                ],
            },
            {"name": '"div"', "props": ["className:sx_3a340e571a_c"], "children": []},
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "inline-grid",
            "verticalAlign": "top",
            "gridAutoFlow": "column",
            "gridAutoColumns": "1fr",
            "alignItems": "stretch",
            "color": "var(--gray-12)",
            "backgroundColor": "var(--color-surface)",
            "backgroundImage": "linear-gradient(var(--gray-a3), var(--gray-a3))",
            "position": "relative",
            "minWidth": "max-content",
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "center",
            "isolation": "isolate",
            "borderRadius": "var(--segmented-control-border-radius)",
            "--rx-segmented-indicator": {
                "default": "none",
                ":has(> label > input:checked)": "block",
            },
            "--rx-segmented-index": {
                "default": "var(--rx-segmented-index-of-value, 0)",
                ":has(> :nth-child(1) > input:checked)": 0,
                ":has(> :nth-child(2) > input:checked)": 1,
                ":has(> :nth-child(3) > input:checked)": 2,
                ":has(> :nth-child(4) > input:checked)": 3,
                ":has(> :nth-child(5) > input:checked)": 4,
                ":has(> :nth-child(6) > input:checked)": 5,
                ":has(> :nth-child(7) > input:checked)": 6,
                ":has(> :nth-child(8) > input:checked)": 7,
                ":has(> :nth-child(9) > input:checked)": 8,
                ":has(> :nth-child(10) > input:checked)": 9,
            },
            "--rx-segmented-separator-duration": {
                "default": "80ms",
                ":has(:focus-visible)": "0ms",
            },
            "--segmented-control-border-radius": "max(var(--radius-3), var(--radius-full))",
            "height": "var(--space-7)",
            "--rx-segmented-font-size": "var(--font-size-3)",
            "--rx-segmented-letter-spacing": "var(--letter-spacing-3)",
            "--rx-segmented-padding": "var(--space-4)",
            "--rx-segmented-gap": "var(--space-3)",
            "--rx-segmented-count": 2,
        },
        {
            "display": "flex",
            "alignItems": "stretch",
            "userSelect": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": "var(--cursor-button)",
            "WebkitTapHighlightColor": "transparent",
            "borderTopLeftRadius": {
                ":first-child": "inherit",
                ":has(> input:focus-visible)": "inherit",
            },
            "borderBottomLeftRadius": {
                ":first-child": "inherit",
                ":has(> input:focus-visible)": "inherit",
            },
            "borderTopRightRadius": {
                ":nth-last-child(2)": "inherit",
                ":has(> input:focus-visible)": "inherit",
            },
            "borderBottomRightRadius": {
                ":nth-last-child(2)": "inherit",
                ":has(> input:focus-visible)": "inherit",
            },
            "outlineWidth": {":has(> input:focus-visible)": "2px"},
            "outlineStyle": {":has(> input:focus-visible)": "solid"},
            "outlineColor": {":has(> input:focus-visible)": "var(--focus-8)"},
            "outlineOffset": {":has(> input:focus-visible)": "-1px"},
            "--rx-segmented-active-opacity": {"default": 0, ":has(> input:checked)": 1},
            "--rx-segmented-inactive-opacity": {
                "default": 1,
                ":has(> input:checked)": 0,
            },
            "--rx-segmented-active-easing": {
                "default": "ease-in",
                ":has(> input:checked)": "ease-out",
            },
            "--rx-segmented-inactive-easing": {
                "default": "ease-out",
                ":has(> input:checked)": "ease-in",
            },
            "--rx-segmented-hover": {
                "@media (hover: hover)": {
                    ":hover:not(:has(> input:checked))": "var(--gray-a2)"
                }
            },
        },
        {
            "appearance": "none",
            "position": "absolute",
            "top": "0",
            "right": "0",
            "bottom": "0",
            "left": "0",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "opacity": 0,
            "pointerEvents": "none",
        },
        {
            "zIndex": -1,
            "marginTop": "3px",
            "marginBottom": "3px",
            "marginLeft": "-0.5px",
            "marginRight": "-0.5px",
            "width": "1px",
            "backgroundColor": "var(--gray-a4)",
            "opacity": "var(--rx-segmented-separator-opacity, 1)",
            "transitionProperty": "opacity",
            "transitionDuration": "var(--rx-segmented-separator-duration)",
            "transitionTimingFunction": "var(--rx-segmented-separator-easing, ease-out)",
        },
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexGrow": 1,
            "alignItems": "center",
            "justifyContent": "center",
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "fontSize": "var(--rx-segmented-font-size)",
            "letterSpacing": "var(--rx-segmented-letter-spacing)",
            "paddingLeft": "var(--rx-segmented-padding)",
            "paddingRight": "var(--rx-segmented-padding)",
            "gap": "var(--rx-segmented-gap)",
            "backgroundColor": "var(--rx-segmented-hover, transparent)",
        },
        {
            "transitionProperty": "opacity",
            "transitionDuration": "80ms",
            "transitionTimingFunction": "var(--rx-segmented-active-easing)",
            "fontWeight": "var(--font-weight-medium)",
            "letterSpacing": "var(--tab-active-letter-spacing)",
            "wordSpacing": "var(--tab-active-word-spacing)",
            "opacity": "var(--rx-segmented-active-opacity)",
        },
        {
            "position": "absolute",
            "transitionProperty": "opacity",
            "transitionDuration": "80ms",
            "transitionTimingFunction": "var(--rx-segmented-inactive-easing)",
            "fontWeight": "var(--font-weight-regular)",
            "letterSpacing": "var(--tab-inactive-letter-spacing)",
            "wordSpacing": "var(--tab-inactive-word-spacing)",
            "opacity": "var(--rx-segmented-inactive-opacity)",
        },
        {
            "display": "flex",
            "alignItems": "stretch",
            "userSelect": "none",
            "marginTop": "1px",
            "marginRight": "1px",
            "marginBottom": "1px",
            "marginLeft": "1px",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": "var(--cursor-button)",
            "WebkitTapHighlightColor": "transparent",
            "borderTopLeftRadius": {
                ":first-child": "inherit",
                ":has(> input:focus-visible)": "inherit",
            },
            "borderBottomLeftRadius": {
                ":first-child": "inherit",
                ":has(> input:focus-visible)": "inherit",
            },
            "borderTopRightRadius": {
                ":nth-last-child(2)": "inherit",
                ":has(> input:focus-visible)": "inherit",
            },
            "borderBottomRightRadius": {
                ":nth-last-child(2)": "inherit",
                ":has(> input:focus-visible)": "inherit",
            },
            "outlineWidth": {":has(> input:focus-visible)": "2px"},
            "outlineStyle": {":has(> input:focus-visible)": "solid"},
            "outlineColor": {":has(> input:focus-visible)": "var(--focus-8)"},
            "outlineOffset": {":has(> input:focus-visible)": "-1px"},
            "--rx-segmented-active-opacity": {"default": 0, ":has(> input:checked)": 1},
            "--rx-segmented-inactive-opacity": {
                "default": 1,
                ":has(> input:checked)": 0,
            },
            "--rx-segmented-active-easing": {
                "default": "ease-in",
                ":has(> input:checked)": "ease-out",
            },
            "--rx-segmented-inactive-easing": {
                "default": "ease-out",
                ":has(> input:checked)": "ease-in",
            },
            "--rx-segmented-hover": {
                "@media (hover: hover)": {
                    ":hover:not(:has(> input:checked))": "var(--gray-a2)"
                }
            },
        },
        {
            "appearance": "none",
            "position": "absolute",
            "top": "0",
            "right": "0",
            "bottom": "0",
            "left": "0",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "opacity": 0,
            "pointerEvents": "none",
        },
        {
            "zIndex": -1,
            "marginTop": "3px",
            "marginBottom": "3px",
            "marginLeft": "-0.5px",
            "marginRight": "-0.5px",
            "width": "1px",
            "backgroundColor": "var(--gray-a4)",
            "opacity": "var(--rx-segmented-separator-opacity, 1)",
            "transitionProperty": "opacity",
            "transitionDuration": "var(--rx-segmented-separator-duration)",
            "transitionTimingFunction": "var(--rx-segmented-separator-easing, ease-out)",
        },
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexGrow": 1,
            "alignItems": "center",
            "justifyContent": "center",
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "fontSize": "var(--rx-segmented-font-size)",
            "letterSpacing": "var(--rx-segmented-letter-spacing)",
            "paddingLeft": "var(--rx-segmented-padding)",
            "paddingRight": "var(--rx-segmented-padding)",
            "gap": "var(--rx-segmented-gap)",
            "backgroundColor": "var(--rx-segmented-hover, transparent)",
        },
        {
            "transitionProperty": "opacity",
            "transitionDuration": "80ms",
            "transitionTimingFunction": "var(--rx-segmented-active-easing)",
            "fontWeight": "var(--font-weight-medium)",
            "letterSpacing": "var(--tab-active-letter-spacing)",
            "wordSpacing": "var(--tab-active-word-spacing)",
            "opacity": "var(--rx-segmented-active-opacity)",
        },
        {
            "position": "absolute",
            "transitionProperty": "opacity",
            "transitionDuration": "80ms",
            "transitionTimingFunction": "var(--rx-segmented-inactive-easing)",
            "fontWeight": "var(--font-weight-regular)",
            "letterSpacing": "var(--tab-inactive-letter-spacing)",
            "wordSpacing": "var(--tab-inactive-word-spacing)",
            "opacity": "var(--rx-segmented-inactive-opacity)",
        },
        {
            "display": "var(--rx-segmented-indicator)",
            "position": {"default": "absolute", "::before": "absolute"},
            "zIndex": -1,
            "top": {"default": "0", "::before": "1px"},
            "left": {"default": "0", "::before": "1px"},
            "height": "100%",
            "width": "calc(100% / var(--rx-segmented-count))",
            "transform": "translateX(calc(var(--rx-segmented-index) * 100%))",
            "pointerEvents": "none",
            "transitionProperty": "transform",
            "transitionTimingFunction": "cubic-bezier(0.445, 0.05, 0.55, 0.95)",
            "transitionDuration": "100ms",
            "right": {"::before": "1px"},
            "bottom": {"::before": "1px"},
            "borderRadius": {
                "::before": "max(0.5px, calc(var(--segmented-control-border-radius) - 1px))"
            },
            "backgroundColor": {
                "::before": "light-dark(var(--color-background), var(--gray-a3))"
            },
            "content": {"::before": "''"},
            "boxShadow": {"::before": "var(--shadow-2)"},
        },
    ]


def test_segmented_control_unknown_variant(ui_plugin: UIPlugin):
    """A variant a segmented control does not have is an error that lists the ones it has."""
    with pytest.raises(StyleError) as error:
        rx.ui.segmented_control.root(variant="soft")
    assert (
        str(error.value)
        == 'rx.ui.segmented_control_root: unknown variant "soft". The values are "classic", "surface".'
    )


def test_segmented_control_from_a_foreach(ui_plugin: UIPlugin):
    """Items a foreach renders are counted in the browser, and a bound control checks the item of its value."""
    control = rx.ui.segmented_control.root(
        rx.foreach(
            SegmentedState.views,
            lambda view: rx.ui.segmented_control.item(view, value=view),
        ),
        value=SegmentedState.view,
        on_change=SegmentedState.set_view,
    )
    state = (
        "reflex___state____state__tests___units___reflex_components_ui"
        "___components___test_segmented_control____segmented_state"
    )
    style = control._element_styles().style.style
    assert str(style["--rx-segmented-count"]) == f"{state}.views_rx_state_.length"
    # The name of the argument of the function is made up anew each run.
    index = re.sub(
        r"\(\((\w+)\) => \1\)",
        "((item) => item)",
        str(style["--rx-segmented-index-of-value"]),
    )
    assert index == (
        f"({state}.views_rx_state_.map(((item) => item))"
        f".indexOf({state}.view_rx_state_))"
    )
    item = control.children[0].children[0]
    assert item.children[0].render()["props"] == [
        f"checked:({state}.view_rx_state_ === view_rx_state_)",
        "className:sx_8e51139181_c",
        'form:""',
        'name:"rx-segmented-1"',
        "readOnly:true",
        'type:"radio"',
        "value:view_rx_state_",
    ]


def test_segmented_control_places_every_item(ui_plugin: UIPlugin):
    """The style table places the indicator for ten items, and a control with more adds the rest."""
    item = rx.ui.segmented_control.item
    twelve = rx.ui.segmented_control.root(*[
        item(str(number), value=str(number)) for number in range(12)
    ])
    index = twelve._element_styles().style.style["--rx-segmented-index"]
    assert index == {
        "default": "var(--rx-segmented-index-of-value, 0)",
        **{
            f":has(> :nth-child({position}) > input:checked)": position - 1
            for position in range(1, 13)
        },
    }
    assert twelve._element_styles().style.style["--rx-segmented-count"] == 12


def test_segmented_control_script(ui_plugin: UIPlugin):
    """The one script of a segmented control is the keys that move through it."""
    control = rx.ui.segmented_control.root(rx.ui.segmented_control.item("a", value="a"))
    assert control._get_all_imports()["$/reflex-ui/behaviors/roving-focus.js"] == [
        ImportVar(tag="rovingKeyDown")
    ]
    assert control.render()["props"] == [
        "className:sx_1b6d0f2eb5_c",
        "onKeyDown:rovingKeyDown",
        'role:"radiogroup"',
    ]
