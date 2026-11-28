"""Tests for reflex_components_ui.components.tabs."""

import itertools
from collections.abc import Callable
from typing import Any, Literal

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.components import tabs as tabs_module
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


@pytest.fixture(autouse=True)
def ids(monkeypatch: pytest.MonkeyPatch):
    """Number the tabs of each test from one."""
    monkeypatch.setattr(tabs_module, "_ids", itertools.count(1))


class TabsState(rx.State):
    """What tabs are bound to."""

    tab: str = "two"
    names: list[str] = ["one", "two"]
    upright: Literal["horizontal", "vertical"] = "vertical"

    @rx.event
    def set_tab(self, tab: str):
        """Follow the tabs.

        Args:
            tab: The value of the selected tab.
        """
        self.tab = tab


def test_tabs(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """The root gives each trigger and panel its id, its state and its orientation; a trigger is a button around its text twice."""
    component = rx.ui.tabs.root(
        rx.ui.tabs.list(
            rx.ui.tabs.trigger("One", value="one", color_scheme="ruby"),
            rx.ui.tabs.trigger("Two", value="two", disabled=True, id="second"),
            size="1",
            loop=False,
        ),
        rx.ui.tabs.content("First", value="one", margin="1px"),
        rx.ui.tabs.content("Second", value="two", id="panel"),
        default_value="one",
        orientation="vertical",
        dir="rtl",
        activation_mode="manual",
        id="tabs",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_293eff2a48_c",
            '"data-activation":"manual"',
            '"data-rx-tabs":""',
            'dir:"rtl"',
            'id:"tabs"',
            "onBlur:tabsEvent",
            "onClick:tabsEvent",
            "onFocus:tabsEvent",
            "ref:ref_tabs",
        ],
        "children": [
            {
                "name": '"div"',
                "props": [
                    '"aria-orientation":"vertical"',
                    "className:sx_52bb344f95_c",
                    '"data-loop":false',
                    "onKeyDown:rovingKeyDown",
                    'role:"tablist"',
                ],
                "children": [
                    {
                        "name": '"button"',
                        "props": [
                            '"aria-controls":"rx-tabs-1-content-one"',
                            '"aria-selected":true',
                            'className:sx_92e2216116_c + " " + reflexUIClasses_e201574881',
                            '"data-state":"active"',
                            '"data-value":"one"',
                            'id:"rx-tabs-1-trigger-one"',
                            'role:"tab"',
                            "tabIndex:0",
                            'type:"button"',
                        ],
                        "children": [
                            {
                                "name": '"span"',
                                "props": ["className:sx_dc646325ab_c"],
                                "children": [{"contents": '"One"'}],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_09d7e7be39_c"],
                                "children": [{"contents": '"One"'}],
                            },
                        ],
                    },
                    {
                        "name": '"button"',
                        "props": [
                            '"aria-controls":"panel"',
                            '"aria-selected":false',
                            "className:sx_92e2216116_c",
                            '"data-state":"inactive"',
                            '"data-value":"two"',
                            "disabled:true",
                            'id:"second"',
                            "ref:ref_second",
                            'role:"tab"',
                            "tabIndex:-1",
                            'type:"button"',
                        ],
                        "children": [
                            {
                                "name": '"span"',
                                "props": ["className:sx_dc646325ab_c"],
                                "children": [{"contents": '"Two"'}],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_09d7e7be39_c"],
                                "children": [{"contents": '"Two"'}],
                            },
                        ],
                    },
                ],
            },
            {
                "name": '"div"',
                "props": [
                    '"aria-labelledby":"rx-tabs-1-trigger-one"',
                    "className:sx_f078fdbeec_c",
                    '"data-rx-tabs-content":""',
                    '"data-state":"active"',
                    '"data-value":"one"',
                    "hidden:false",
                    'id:"rx-tabs-1-content-one"',
                    'role:"tabpanel"',
                    "tabIndex:0",
                ],
                "children": [{"contents": '"First"'}],
            },
            {
                "name": '"div"',
                "props": [
                    '"aria-labelledby":"second"',
                    "className:sx_dd03223cd1_c",
                    '"data-rx-tabs-content":""',
                    '"data-state":"inactive"',
                    '"data-value":"two"',
                    "hidden:true",
                    'id:"panel"',
                    "ref:ref_panel",
                    'role:"tabpanel"',
                    "tabIndex:0",
                ],
                "children": [{"contents": '"Second"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {"display": "flex"},
        {
            "display": {"default": "block", "::-webkit-scrollbar": "none"},
            "justifyContent": "flex-start",
            "overflowX": "auto",
            "whiteSpace": "nowrap",
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "scrollbarWidth": "none",
            "boxShadow": "inset -1px 0 0 0 var(--gray-a5)",
            "fontSize": "var(--font-size-1)",
            "lineHeight": "var(--line-height-1)",
            "letterSpacing": "var(--letter-spacing-1)",
            "--tab-height": "var(--space-6)",
            "--tab-padding-x": "var(--space-1)",
            "--tab-inner-padding-x": "var(--space-1)",
            "--tab-inner-padding-y": "calc(var(--space-1) * 0.5)",
            "--tab-inner-border-radius": "var(--radius-1)",
        },
        {
            "appearance": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingBottom": "0",
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
                "::before": {"[aria-selected='true']": "var(--accent-indicator)"},
            },
            "backgroundImage": "none",
            "fontFamily": "inherit",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "wordSpacing": "inherit",
            "textTransform": "inherit",
            "textAlign": "inherit",
            "textIndent": "initial",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "cursor": {
                "default": "var(--cursor-button)",
                ":disabled": "var(--cursor-disabled)",
            },
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "WebkitTapHighlightColor": "transparent",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "flexShrink": 0,
            "position": {
                "default": "relative",
                "::before": {"[aria-selected='true']": "absolute"},
            },
            "userSelect": "none",
            "boxSizing": {
                "default": "border-box",
                "::before": {"[aria-selected='true']": "border-box"},
            },
            "height": {
                "default": "var(--tab-height)",
                "::before": {"[aria-selected='true']": "2px"},
            },
            "paddingLeft": "var(--tab-padding-x)",
            "paddingRight": "var(--tab-padding-x)",
            "color": {
                "default": "var(--gray-a11)",
                "@media (hover: hover)": {":hover": "var(--gray-12)"},
                "[aria-selected='true']": "var(--gray-12)",
            },
            "--rx-tab-font-weight": {
                "[aria-selected='true']": "var(--font-weight-medium)"
            },
            "--rx-tab-letter-spacing": {
                "default": "var(--tab-inactive-letter-spacing)",
                "[aria-selected='true']": "var(--tab-active-letter-spacing)",
            },
            "--rx-tab-word-spacing": {
                "default": "var(--tab-inactive-word-spacing)",
                "[aria-selected='true']": "var(--tab-active-word-spacing)",
            },
            "--rx-tab-fill": {
                "@media (hover: hover)": {
                    ":hover:not(:focus-visible)": "var(--gray-a3)",
                    ":hover:focus-visible": "var(--accent-a3)",
                }
            },
            "--rx-tab-ring": {":focus-visible": "solid"},
            "--rx-tab-ring-width": {":focus-visible": "2px"},
            "--rx-tab-ring-color": {":focus-visible": "var(--focus-8)"},
            "--rx-tab-ring-offset": {":focus-visible": "-2px"},
            "content": {"::before": {"[aria-selected='true']": "''"}},
            "bottom": {"::before": {"[aria-selected='true']": "0"}},
            "left": {"::before": {"[aria-selected='true']": "0"}},
            "right": {"::before": {"[aria-selected='true']": "0"}},
            "width": "100%",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "boxSizing": "border-box",
            "padding": "var(--tab-inner-padding-y) var(--tab-inner-padding-x)",
            "borderRadius": "var(--tab-inner-border-radius)",
            "position": "absolute",
            "fontWeight": "var(--rx-tab-font-weight, inherit)",
            "letterSpacing": "var(--rx-tab-letter-spacing)",
            "wordSpacing": "var(--rx-tab-word-spacing)",
            "backgroundColor": "var(--rx-tab-fill, transparent)",
            "outlineStyle": "var(--rx-tab-ring, none)",
            "outlineWidth": "var(--rx-tab-ring-width, medium)",
            "outlineColor": "var(--rx-tab-ring-color, currentcolor)",
            "outlineOffset": "var(--rx-tab-ring-offset, 0)",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "boxSizing": "border-box",
            "padding": "var(--tab-inner-padding-y) var(--tab-inner-padding-x)",
            "borderRadius": "var(--tab-inner-border-radius)",
            "visibility": "hidden",
            "fontWeight": "var(--font-weight-medium)",
            "letterSpacing": "var(--tab-active-letter-spacing)",
            "wordSpacing": "var(--tab-active-word-spacing)",
        },
        {
            "appearance": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingBottom": "0",
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
                "::before": {"[aria-selected='true']": "var(--accent-indicator)"},
            },
            "backgroundImage": "none",
            "fontFamily": "inherit",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "wordSpacing": "inherit",
            "textTransform": "inherit",
            "textAlign": "inherit",
            "textIndent": "initial",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "cursor": {
                "default": "var(--cursor-button)",
                ":disabled": "var(--cursor-disabled)",
            },
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "WebkitTapHighlightColor": "transparent",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "flexShrink": 0,
            "position": {
                "default": "relative",
                "::before": {"[aria-selected='true']": "absolute"},
            },
            "userSelect": "none",
            "boxSizing": {
                "default": "border-box",
                "::before": {"[aria-selected='true']": "border-box"},
            },
            "height": {
                "default": "var(--tab-height)",
                "::before": {"[aria-selected='true']": "2px"},
            },
            "paddingLeft": "var(--tab-padding-x)",
            "paddingRight": "var(--tab-padding-x)",
            "color": {
                "default": "var(--gray-a11)",
                "@media (hover: hover)": {":hover": "var(--gray-12)"},
                "[aria-selected='true']": "var(--gray-12)",
            },
            "--rx-tab-font-weight": {
                "[aria-selected='true']": "var(--font-weight-medium)"
            },
            "--rx-tab-letter-spacing": {
                "default": "var(--tab-inactive-letter-spacing)",
                "[aria-selected='true']": "var(--tab-active-letter-spacing)",
            },
            "--rx-tab-word-spacing": {
                "default": "var(--tab-inactive-word-spacing)",
                "[aria-selected='true']": "var(--tab-active-word-spacing)",
            },
            "--rx-tab-fill": {
                "@media (hover: hover)": {
                    ":hover:not(:focus-visible)": "var(--gray-a3)",
                    ":hover:focus-visible": "var(--accent-a3)",
                }
            },
            "--rx-tab-ring": {":focus-visible": "solid"},
            "--rx-tab-ring-width": {":focus-visible": "2px"},
            "--rx-tab-ring-color": {":focus-visible": "var(--focus-8)"},
            "--rx-tab-ring-offset": {":focus-visible": "-2px"},
            "content": {"::before": {"[aria-selected='true']": "''"}},
            "bottom": {"::before": {"[aria-selected='true']": "0"}},
            "left": {"::before": {"[aria-selected='true']": "0"}},
            "right": {"::before": {"[aria-selected='true']": "0"}},
            "width": "100%",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "boxSizing": "border-box",
            "padding": "var(--tab-inner-padding-y) var(--tab-inner-padding-x)",
            "borderRadius": "var(--tab-inner-border-radius)",
            "position": "absolute",
            "fontWeight": "var(--rx-tab-font-weight, inherit)",
            "letterSpacing": "var(--rx-tab-letter-spacing)",
            "wordSpacing": "var(--rx-tab-word-spacing)",
            "backgroundColor": "var(--rx-tab-fill, transparent)",
            "outlineStyle": "var(--rx-tab-ring, none)",
            "outlineWidth": "var(--rx-tab-ring-width, medium)",
            "outlineColor": "var(--rx-tab-ring-color, currentcolor)",
            "outlineOffset": "var(--rx-tab-ring-offset, 0)",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "boxSizing": "border-box",
            "padding": "var(--tab-inner-padding-y) var(--tab-inner-padding-x)",
            "borderRadius": "var(--tab-inner-border-radius)",
            "visibility": "hidden",
            "fontWeight": "var(--font-weight-medium)",
            "letterSpacing": "var(--tab-active-letter-spacing)",
            "wordSpacing": "var(--tab-active-word-spacing)",
        },
        {
            "position": "relative",
            "outlineStyle": {"default": "none", ":focus-visible": "solid"},
            "outlineWidth": {"default": "0", ":focus-visible": "2px"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "width": "100%",
            "marginTop": "1px",
            "marginRight": "1px",
            "marginBottom": "1px",
            "marginLeft": "1px",
        },
        {
            "position": "relative",
            "outlineStyle": {"default": "none", ":focus-visible": "solid"},
            "outlineWidth": {"default": "0", ":focus-visible": "2px"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "width": "100%",
        },
    ]


def test_tabs_without_a_value(ui_plugin: UIPlugin):
    """Tab stops on the first trigger that is not disabled, and tabs inside a panel are their own."""
    component = rx.ui.tabs.root(
        rx.ui.tabs.list(
            rx.ui.tabs.trigger("Off", value="off", disabled=True),
            rx.ui.tabs.trigger("On", value="on"),
        ),
        rx.ui.tabs.content(
            rx.ui.tabs(
                rx.ui.tabs.list(rx.ui.tabs.trigger("In", value="in")),
                rx.ui.tabs.content("Inner", value="in"),
                default_value="in",
            ),
            value="on",
        ),
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            '"data-rx-tabs":""',
            "onBlur:tabsEvent",
            "onClick:tabsEvent",
            "onFocus:tabsEvent",
        ],
        "children": [
            {
                "name": '"div"',
                "props": [
                    '"aria-orientation":"horizontal"',
                    "className:sx_4f6024971d_c",
                    "onKeyDown:rovingKeyDown",
                    'role:"tablist"',
                ],
                "children": [
                    {
                        "name": '"button"',
                        "props": [
                            '"aria-controls":"rx-tabs-2-content-off"',
                            '"aria-selected":false',
                            "className:sx_585a0027e5_c",
                            '"data-state":"inactive"',
                            '"data-value":"off"',
                            "disabled:true",
                            'id:"rx-tabs-2-trigger-off"',
                            'role:"tab"',
                            "tabIndex:-1",
                            'type:"button"',
                        ],
                        "children": [
                            {
                                "name": '"span"',
                                "props": ["className:sx_dc646325ab_c"],
                                "children": [{"contents": '"Off"'}],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_09d7e7be39_c"],
                                "children": [{"contents": '"Off"'}],
                            },
                        ],
                    },
                    {
                        "name": '"button"',
                        "props": [
                            '"aria-controls":"rx-tabs-2-content-on"',
                            '"aria-selected":false',
                            "className:sx_585a0027e5_c",
                            '"data-state":"inactive"',
                            '"data-value":"on"',
                            'id:"rx-tabs-2-trigger-on"',
                            'role:"tab"',
                            "tabIndex:0",
                            'type:"button"',
                        ],
                        "children": [
                            {
                                "name": '"span"',
                                "props": ["className:sx_dc646325ab_c"],
                                "children": [{"contents": '"On"'}],
                            },
                            {
                                "name": '"span"',
                                "props": ["className:sx_09d7e7be39_c"],
                                "children": [{"contents": '"On"'}],
                            },
                        ],
                    },
                ],
            },
            {
                "name": '"div"',
                "props": [
                    '"aria-labelledby":"rx-tabs-2-trigger-on"',
                    "className:sx_b59d991c6f_c",
                    '"data-rx-tabs-content":""',
                    '"data-state":"inactive"',
                    '"data-value":"on"',
                    "hidden:true",
                    'id:"rx-tabs-2-content-on"',
                    'role:"tabpanel"',
                    "tabIndex:0",
                ],
                "children": [
                    {
                        "name": '"div"',
                        "props": [
                            '"data-rx-tabs":""',
                            "onBlur:tabsEvent",
                            "onClick:tabsEvent",
                            "onFocus:tabsEvent",
                        ],
                        "children": [
                            {
                                "name": '"div"',
                                "props": [
                                    '"aria-orientation":"horizontal"',
                                    "className:sx_4f6024971d_c",
                                    "onKeyDown:rovingKeyDown",
                                    'role:"tablist"',
                                ],
                                "children": [
                                    {
                                        "name": '"button"',
                                        "props": [
                                            '"aria-controls":"rx-tabs-1-content-in"',
                                            '"aria-selected":true',
                                            "className:sx_585a0027e5_c",
                                            '"data-state":"active"',
                                            '"data-value":"in"',
                                            'id:"rx-tabs-1-trigger-in"',
                                            'role:"tab"',
                                            "tabIndex:0",
                                            'type:"button"',
                                        ],
                                        "children": [
                                            {
                                                "name": '"span"',
                                                "props": ["className:sx_dc646325ab_c"],
                                                "children": [{"contents": '"In"'}],
                                            },
                                            {
                                                "name": '"span"',
                                                "props": ["className:sx_09d7e7be39_c"],
                                                "children": [{"contents": '"In"'}],
                                            },
                                        ],
                                    }
                                ],
                            },
                            {
                                "name": '"div"',
                                "props": [
                                    '"aria-labelledby":"rx-tabs-1-trigger-in"',
                                    "className:sx_b59d991c6f_c",
                                    '"data-rx-tabs-content":""',
                                    '"data-state":"active"',
                                    '"data-value":"in"',
                                    "hidden:false",
                                    'id:"rx-tabs-1-content-in"',
                                    'role:"tabpanel"',
                                    "tabIndex:0",
                                ],
                                "children": [{"contents": '"Inner"'}],
                            },
                        ],
                    }
                ],
            },
        ],
    }


def test_tabs_trigger_alone(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A trigger outside tabs is one that is not selected."""
    component = rx.ui.tabs.trigger("Alone", value="alone")
    assert component.render() == {
        "name": '"button"',
        "props": [
            '"aria-selected":false',
            "className:sx_585a0027e5_c",
            '"data-state":"inactive"',
            '"data-value":"alone"',
            'role:"tab"',
            "tabIndex:-1",
            'type:"button"',
        ],
        "children": [
            {
                "name": '"span"',
                "props": ["className:sx_dc646325ab_c"],
                "children": [{"contents": '"Alone"'}],
            },
            {
                "name": '"span"',
                "props": ["className:sx_09d7e7be39_c"],
                "children": [{"contents": '"Alone"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "appearance": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingBottom": "0",
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
                "::before": {"[aria-selected='true']": "var(--accent-indicator)"},
            },
            "backgroundImage": "none",
            "fontFamily": "inherit",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "wordSpacing": "inherit",
            "textTransform": "inherit",
            "textAlign": "inherit",
            "textIndent": "initial",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "cursor": {
                "default": "var(--cursor-button)",
                ":disabled": "var(--cursor-disabled)",
            },
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "WebkitTapHighlightColor": "transparent",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "flexShrink": 0,
            "position": {
                "default": "relative",
                "::before": {"[aria-selected='true']": "absolute"},
            },
            "userSelect": "none",
            "boxSizing": {
                "default": "border-box",
                "::before": {"[aria-selected='true']": "border-box"},
            },
            "height": {
                "default": "var(--tab-height)",
                "::before": {"[aria-selected='true']": "2px"},
            },
            "paddingLeft": "var(--tab-padding-x)",
            "paddingRight": "var(--tab-padding-x)",
            "color": {
                "default": "var(--gray-a11)",
                "@media (hover: hover)": {":hover": "var(--gray-12)"},
                "[aria-selected='true']": "var(--gray-12)",
            },
            "--rx-tab-font-weight": {
                "[aria-selected='true']": "var(--font-weight-medium)"
            },
            "--rx-tab-letter-spacing": {
                "default": "var(--tab-inactive-letter-spacing)",
                "[aria-selected='true']": "var(--tab-active-letter-spacing)",
            },
            "--rx-tab-word-spacing": {
                "default": "var(--tab-inactive-word-spacing)",
                "[aria-selected='true']": "var(--tab-active-word-spacing)",
            },
            "--rx-tab-fill": {
                "@media (hover: hover)": {
                    ":hover:not(:focus-visible)": "var(--gray-a3)",
                    ":hover:focus-visible": "var(--accent-a3)",
                }
            },
            "--rx-tab-ring": {":focus-visible": "solid"},
            "--rx-tab-ring-width": {":focus-visible": "2px"},
            "--rx-tab-ring-color": {":focus-visible": "var(--focus-8)"},
            "--rx-tab-ring-offset": {":focus-visible": "-2px"},
            "content": {"::before": {"[aria-selected='true']": "''"}},
            "bottom": {"::before": {"[aria-selected='true']": "0"}},
            "left": {"::before": {"[aria-selected='true']": "0"}},
            "right": {"::before": {"[aria-selected='true']": "0"}},
        },
        {
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "boxSizing": "border-box",
            "padding": "var(--tab-inner-padding-y) var(--tab-inner-padding-x)",
            "borderRadius": "var(--tab-inner-border-radius)",
            "position": "absolute",
            "fontWeight": "var(--rx-tab-font-weight, inherit)",
            "letterSpacing": "var(--rx-tab-letter-spacing)",
            "wordSpacing": "var(--rx-tab-word-spacing)",
            "backgroundColor": "var(--rx-tab-fill, transparent)",
            "outlineStyle": "var(--rx-tab-ring, none)",
            "outlineWidth": "var(--rx-tab-ring-width, medium)",
            "outlineColor": "var(--rx-tab-ring-color, currentcolor)",
            "outlineOffset": "var(--rx-tab-ring-offset, 0)",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "boxSizing": "border-box",
            "padding": "var(--tab-inner-padding-y) var(--tab-inner-padding-x)",
            "borderRadius": "var(--tab-inner-border-radius)",
            "visibility": "hidden",
            "fontWeight": "var(--font-weight-medium)",
            "letterSpacing": "var(--tab-active-letter-spacing)",
            "wordSpacing": "var(--tab-active-word-spacing)",
        },
    ]


def test_tabs_content_alone(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A panel outside tabs is one that is not shown."""
    component = rx.ui.tabs.content("Alone", value="alone")
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_b59d991c6f_c",
            '"data-rx-tabs-content":""',
            '"data-state":"inactive"',
            '"data-value":"alone"',
            "hidden:true",
            'role:"tabpanel"',
            "tabIndex:0",
        ],
        "children": [{"contents": '"Alone"'}],
    }
    assert declared_styles(component) == [
        {
            "position": "relative",
            "outlineStyle": {"default": "none", ":focus-visible": "solid"},
            "outlineWidth": {"default": "0", ":focus-visible": "2px"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
        }
    ]


def test_tabs_list_alone(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A list outside tabs is horizontal."""
    component = rx.ui.tabs.list()
    assert component.render() == {
        "name": '"div"',
        "props": [
            '"aria-orientation":"horizontal"',
            "className:sx_4f6024971d_c",
            "onKeyDown:rovingKeyDown",
            'role:"tablist"',
        ],
        "children": [],
    }
    assert declared_styles(component) == [
        {
            "display": {"default": "flex", "::-webkit-scrollbar": "none"},
            "justifyContent": "flex-start",
            "overflowX": "auto",
            "whiteSpace": "nowrap",
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "scrollbarWidth": "none",
            "boxShadow": "inset 0 -1px 0 0 var(--gray-a5)",
            "fontSize": "var(--font-size-2)",
            "lineHeight": "var(--line-height-2)",
            "letterSpacing": "var(--letter-spacing-2)",
            "--tab-height": "var(--space-7)",
            "--tab-padding-x": "var(--space-2)",
            "--tab-inner-padding-x": "var(--space-2)",
            "--tab-inner-padding-y": "var(--space-1)",
            "--tab-inner-border-radius": "var(--radius-2)",
        }
    ]


def test_tabs_bound_to_state(ui_plugin: UIPlugin):
    """Tabs bound to state render their state as expressions, hand the script what they do on a change, and keep a handler of their own for a press."""
    selected, upright = str(TabsState.tab), str(TabsState.upright)
    on_change = (
        f'((_ev_0) => (addEvents([(ReflexEvent("{TabsState.get_full_name()}.set_tab", '
        '({ ["tab"] : _ev_0 }), ({  })))], [_ev_0], ({  }))))'
    )
    component = rx.ui.tabs.root(
        rx.ui.tabs.list(
            rx.foreach(
                TabsState.names, lambda name: rx.ui.tabs.trigger(name, value=name)
            )
        ),
        rx.foreach(TabsState.names, lambda name: rx.ui.tabs.content(name, value=name)),
        value=TabsState.tab,
        on_change=TabsState.set_tab,
        orientation=TabsState.upright,
        on_click=rx.console_log("pressed"),
    )
    rendered = component.render()
    assert rendered["props"] == [
        f'className:(sx_8b94b45675_0[{upright}] ?? "")',
        '"data-rx-tabs":"bound"',
        f"onBlur:((event) => tabsEvent(event, {on_change}))",
        (
            f"onClick:((event) => {{ (((event) => tabsEvent(event, {on_change})))(event); "
            '(((_e) => (addEvents([(ReflexEvent("_call_function", ({ ["function"] : '
            '(() => (console?.["log"]("pressed"))), ["callback"] : null }), ({  })))], '
            "[_e], ({  })))))(event); })"
        ),
        f"onFocus:((event) => tabsEvent(event, {on_change}))",
    ]
    tab_list, panels = rendered["children"]
    assert tab_list["props"] == [
        f'"aria-orientation":{upright}',
        f'className:sx_e6dbf978a8_c + " " + (sx_e6dbf978a8_0[{upright}] ?? sx_e6dbf978a8_0d)',
        "onKeyDown:rovingKeyDown",
        'role:"tablist"',
    ]
    index = tab_list["children"][0]["index_var_name"]
    assert tab_list["children"][0]["children"] == [
        {
            "name": '"button"',
            "props": [
                '"aria-controls":("rx-tabs-1-content-" + name_rx_state_)',
                f'"aria-selected":({selected} === name_rx_state_)',
                f'className:sx_bbc606ee2b_c + " " + (sx_bbc606ee2b_0[{upright}] ?? "")',
                f'"data-state":(({selected} === name_rx_state_) ? "active" : "inactive")',
                '"data-value":name_rx_state_',
                'id:("rx-tabs-1-trigger-" + name_rx_state_)',
                f"key:{index}",
                'role:"tab"',
                f"tabIndex:(({selected} === name_rx_state_) ? 0 : -1)",
                'type:"button"',
            ],
            "children": [
                {
                    "name": '"span"',
                    "props": ["className:sx_dc646325ab_c"],
                    "children": [{"contents": "name_rx_state_"}],
                },
                {
                    "name": '"span"',
                    "props": ["className:sx_09d7e7be39_c"],
                    "children": [{"contents": "name_rx_state_"}],
                },
            ],
        }
    ]
    assert panels["children"] == [
        {
            "name": '"div"',
            "props": [
                '"aria-labelledby":("rx-tabs-1-trigger-" + name_rx_state_)',
                f'className:sx_c229fddc7e_c + " " + (sx_c229fddc7e_0[{upright}] ?? "")',
                '"data-rx-tabs-content":""',
                f'"data-state":(({selected} === name_rx_state_) ? "active" : "inactive")',
                '"data-value":name_rx_state_',
                f"hidden:(({selected} === name_rx_state_) ? false : true)",
                'id:("rx-tabs-1-content-" + name_rx_state_)',
                f"key:{panels['index_var_name']}",
                'role:"tabpanel"',
                "tabIndex:0",
            ],
            "children": [{"contents": "name_rx_state_"}],
        }
    ]


def test_tabs_import_their_scripts(ui_plugin: UIPlugin):
    """A page with tabs loads the script that selects a tab and the one of the arrow keys, and nothing else of a script."""
    component = rx.ui.tabs.root(
        rx.ui.tabs.list(rx.ui.tabs.trigger("One", value="one")),
        rx.ui.tabs.content("First", value="one"),
    )
    imports = component._get_all_imports()
    assert {
        module: names for module, names in imports.items() if "behaviors" in module
    } == {
        "$/reflex-ui/behaviors/tabs.js": [ImportVar(tag="tabsEvent")],
        "$/reflex-ui/behaviors/roving-focus.js": [ImportVar(tag="rovingKeyDown")],
    }


def test_tabs_refuse_a_size_they_do_not_have(ui_plugin: UIPlugin):
    """A value a prop does not take fails with the name of the component and the values."""
    with pytest.raises(StyleError) as error:
        rx.ui.tabs.list(size="3")
    assert str(error.value) == (
        'rx.ui.tabs_list: unknown size "3". The values are "1", "2".'
    )
