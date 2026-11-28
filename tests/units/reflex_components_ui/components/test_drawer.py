"""Tests for reflex_components_ui.components.drawer."""

import itertools
from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.components import _dialog
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


@pytest.fixture(autouse=True)
def ids(monkeypatch: pytest.MonkeyPatch):
    """Number the drawers of each test from one."""
    monkeypatch.setattr(_dialog, "_ids", itertools.count(1))


def test_drawer(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A drawer is a native dialog around the panel an app styles, which slides in from the edge the root names; its overlay is an element of its own beside it, and its portal is nothing."""
    component = rx.ui.drawer.root(
        rx.ui.drawer.trigger(rx.el.button("Open")),
        rx.ui.drawer.overlay(z_index="5"),
        rx.ui.drawer.portal(
            rx.ui.drawer.content(
                rx.ui.drawer.handle(),
                rx.ui.drawer.title("Settings"),
                rx.ui.drawer.description("What it is about."),
                rx.ui.drawer.close(rx.el.button("Close")),
                right="auto",
                width="20em",
                background_color="white",
            )
        ),
        direction="left",
        on_animation_end=rx.console_log("moved"),
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_71b84cd269_c",
            '"data-rx-dialog-root":""',
            "onClick:dialogClick",
        ],
        "children": [
            {
                "name": '"button"',
                "props": [
                    '"aria-controls":"rx-dialog-1"',
                    '"aria-expanded":false',
                    '"aria-haspopup":"dialog"',
                    'command:"show-modal"',
                    'commandfor:"rx-dialog-1"',
                    '"data-rx-dialog-trigger":""',
                    '"data-state":"closed"',
                ],
                "children": [{"contents": '"Open"'}],
            },
            {
                "name": '"div"',
                "props": ["className:sx_92fd57a6ed_c", '"data-rx-popup":""'],
                "children": [],
            },
            {
                "name": "Fragment",
                "props": [],
                "children": [
                    {
                        "name": '"dialog"',
                        "props": [
                            '"aria-describedby":"rx-dialog-1-describedby"',
                            '"aria-labelledby":"rx-dialog-1-labelledby"',
                            "className:sx_ec0690f8c2_c",
                            '"data-rx-popup":""',
                            'id:"rx-dialog-1"',
                            "onCancel:dialogEvent",
                            "onClose:dialogEvent",
                            'onTransitionEnd:((event) => event.propertyName === "transform" && event.target.parentElement === event.currentTarget && (((_ev_0) => (addEvents([(ReflexEvent("_call_function", ({ ["function"] : (() => (console?.["log"]("moved"))), ["callback"] : null }), ({  })))], [_ev_0], ({  })))))(event.currentTarget.open))',
                            "ref:((dialog) => dialogSync(dialog, null, null))",
                        ],
                        "children": [
                            {
                                "name": '"div"',
                                "props": ["className:sx_e8c44019a7_c"],
                                "children": [
                                    {
                                        "name": '"div"',
                                        "props": [
                                            '"aria-hidden":true',
                                            "className:sx_c352e99684_c",
                                        ],
                                        "children": [
                                            {
                                                "name": '"span"',
                                                "props": [
                                                    '"aria-hidden":true',
                                                    "className:sx_90a94c0153_c",
                                                ],
                                                "children": [],
                                            }
                                        ],
                                    },
                                    {
                                        "name": '"h2"',
                                        "props": [
                                            "className:sx_0590ef4057_c",
                                            'id:"rx-dialog-1-labelledby"',
                                        ],
                                        "children": [{"contents": '"Settings"'}],
                                    },
                                    {
                                        "name": '"p"',
                                        "props": [
                                            "className:sx_faadb9eee6_c",
                                            'id:"rx-dialog-1-describedby"',
                                        ],
                                        "children": [
                                            {"contents": '"What it is about."'}
                                        ],
                                    },
                                    {
                                        "name": '"button"',
                                        "props": [
                                            'command:"close"',
                                            'commandfor:"rx-dialog-1"',
                                            '"data-rx-dialog-close":""',
                                        ],
                                        "children": [{"contents": '"Close"'}],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {"display": "contents"},
        {},
        {
            "position": "fixed",
            "left": "0",
            "right": "0",
            "bottom": "0",
            "top": "0",
            "zIndex": "5",
            "backgroundColor": "rgba(0, 0, 0, 0.5)",
            "transitionProperty": "opacity, display",
            "transitionDuration": "0.5s",
            "transitionTimingFunction": "cubic-bezier(0.32, 0.72, 0, 1)",
            "display": {
                "default": "none",
                ":is(:has(~ dialog[open]), dialog[open] ~ *)": "block",
            },
            "opacity": {
                "default": 0,
                ":is(:has(~ dialog[open]), dialog[open] ~ *)": {
                    "default": 1,
                    "@starting-style": 0,
                },
            },
        },
        {
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
            "backgroundColor": {"default": "transparent", "::backdrop": "transparent"},
            "color": "inherit",
            "maxWidth": "none",
            "maxHeight": "none",
            "outlineStyle": "none",
            "transitionProperty": "display, overlay",
            "transitionDuration": "0.55s",
            "--rx-dialog-shown": {"default": 0, "[open]": 1},
            "position": "fixed",
            "top": "0",
            "right": "0",
            "bottom": "0",
            "left": "0",
            "width": "100%",
            "height": "100%",
            "zIndex": 50,
            "display": {"default": "none", "[open]": "block"},
            "--rx-drawer-place": {"default": "var(--rx-drawer-away)", "[open]": "none"},
            "--rx-drawer-away": "translate3d(-100%, 0, 0)",
        },
        {
            "left": "0",
            "right": {"default": "auto", "::after": "100%"},
            "bottom": {"default": "0", "::after": "0"},
            "top": {"default": "0", "::after": "0"},
            "position": {"default": "fixed", "::after": "absolute"},
            "zIndex": 50,
            "display": "flex",
            "pointerEvents": "auto",
            "touchAction": "none",
            "willChange": "transform",
            "userSelect": {"@media (hover: hover) and (pointer: fine)": "none"},
            "transform": {
                "default": "var(--rx-drawer-place)",
                "@starting-style": "var(--rx-drawer-away)",
            },
            "transitionProperty": "transform",
            "transitionDuration": "0.5s",
            "transitionTimingFunction": "cubic-bezier(0.32, 0.72, 0, 1)",
            "content": {"::after": "''"},
            "backgroundColor": {"default": "white", "::after": "inherit"},
            "backgroundImage": {"::after": "inherit"},
            "width": {"default": "20em", "::after": "200%"},
        },
        {
            "display": "block",
            "position": "relative",
            "opacity": {"default": 0.7, ":hover": 1, ":active": 1},
            "backgroundColor": "#e2e2e4",
            "marginLeft": "auto",
            "marginRight": "auto",
            "height": "5px",
            "width": "32px",
            "borderTopLeftRadius": "1rem",
            "borderTopRightRadius": "1rem",
            "borderBottomRightRadius": "1rem",
            "borderBottomLeftRadius": "1rem",
            "touchAction": "pan-y",
        },
        {
            "position": "absolute",
            "left": "50%",
            "top": "50%",
            "transform": "translate(-50%, -50%)",
            "width": "max(100%, 2.75rem)",
            "height": "max(100%, 2.75rem)",
            "touchAction": "inherit",
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "fontSize": "1.125rem",
            "fontWeight": "600",
            "lineHeight": "1",
            "letterSpacing": "-0.05em",
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "fontSize": "0.875rem",
        },
        {},
    ]


def test_drawer_that_is_not_modal_nor_dismissible(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A drawer that is not modal lets the pointer through beside its panel and has no overlay, one that is not dismissible says so to its script, and a trigger that is not its child is a button."""
    component = rx.ui.drawer.root(
        rx.ui.drawer.trigger("Open", as_child=False),
        rx.ui.drawer.overlay(),
        rx.ui.drawer.content("Inside"),
        modal=False,
        dismissible=False,
        snap_points=["148px", 1],
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_71b84cd269_c",
            '"data-rx-dialog-root":""',
            "onClick:dialogClick",
        ],
        "children": [
            {
                "name": '"button"',
                "props": [
                    '"aria-controls":"rx-dialog-1"',
                    '"aria-expanded":false',
                    '"aria-haspopup":"dialog"',
                    '"data-rx-dialog-trigger":""',
                    '"data-state":"closed"',
                    'type:"button"',
                ],
                "children": [{"contents": '"Open"'}],
            },
            {
                "name": '"div"',
                "props": ["className:sx_10d19d24da_c", '"data-rx-popup":""'],
                "children": [],
            },
            {
                "name": '"dialog"',
                "props": [
                    "className:sx_9705da5fe6_c",
                    '"data-modal":"false"',
                    '"data-rx-keep":"all"',
                    '"data-rx-popup":""',
                    'id:"rx-dialog-1"',
                    "onCancel:dialogEvent",
                    "onClose:dialogEvent",
                    "ref:((dialog) => dialogSync(dialog, null, null))",
                ],
                "children": [
                    {
                        "name": '"div"',
                        "props": ["className:sx_b169a25bca_c"],
                        "children": [{"contents": '"Inside"'}],
                    }
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {"display": "contents"},
        {},
        {
            "position": "fixed",
            "left": "0",
            "right": "0",
            "bottom": "0",
            "top": "0",
            "zIndex": 50,
            "backgroundColor": "rgba(0, 0, 0, 0.5)",
            "transitionProperty": "opacity, display",
            "transitionDuration": "0.5s",
            "transitionTimingFunction": "cubic-bezier(0.32, 0.72, 0, 1)",
            "display": "none",
        },
        {
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
            "backgroundColor": {"default": "transparent", "::backdrop": "transparent"},
            "color": "inherit",
            "maxWidth": "none",
            "maxHeight": "none",
            "outlineStyle": "none",
            "transitionProperty": "display, overlay",
            "transitionDuration": "0.55s",
            "--rx-dialog-shown": {"default": 0, "[open]": 1},
            "position": "fixed",
            "top": "0",
            "right": "0",
            "bottom": "0",
            "left": "0",
            "width": "100%",
            "height": "100%",
            "zIndex": 50,
            "display": {"default": "none", "[open]": "block"},
            "--rx-drawer-place": {"default": "var(--rx-drawer-away)", "[open]": "none"},
            "--rx-drawer-away": "translate3d(0, 100%, 0)",
            "pointerEvents": "none",
        },
        {
            "left": {"default": "0", "::after": "0"},
            "right": {"default": "0", "::after": "0"},
            "bottom": "0",
            "top": {"default": "0", "::after": "100%"},
            "position": {"default": "fixed", "::after": "absolute"},
            "zIndex": 50,
            "display": "flex",
            "pointerEvents": "auto",
            "touchAction": "none",
            "willChange": "transform",
            "userSelect": {"@media (hover: hover) and (pointer: fine)": "none"},
            "transform": {
                "default": "var(--rx-drawer-place)",
                "@starting-style": "var(--rx-drawer-away)",
            },
            "transitionProperty": "transform",
            "transitionDuration": "0.5s",
            "transitionTimingFunction": "cubic-bezier(0.32, 0.72, 0, 1)",
            "content": {"::after": "''"},
            "backgroundColor": {"::after": "inherit"},
            "backgroundImage": {"::after": "inherit"},
            "height": {"::after": "200%"},
        },
    ]
