"""Tests for reflex_components_ui.components.alert_dialog."""

import itertools
from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.components import _dialog
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


@pytest.fixture(autouse=True)
def ids(monkeypatch: pytest.MonkeyPatch):
    """Number the dialogs of each test from one."""
    monkeypatch.setattr(_dialog, "_ids", itertools.count(1))


def test_alert_dialog(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """An alert dialog is a native dialog with the role of one, which a press beside its panel does not dismiss; what cancels it is marked, and takes the focus when the dialog opens."""
    component = rx.ui.alert_dialog.root(
        rx.ui.alert_dialog.trigger(rx.el.button("Delete")),
        rx.ui.alert_dialog.content(
            rx.ui.alert_dialog.title("Delete the file"),
            rx.ui.alert_dialog.description("It cannot be brought back."),
            rx.ui.alert_dialog.action(rx.el.button("Delete it")),
            rx.ui.alert_dialog.cancel(rx.el.button("Keep it")),
            size="1",
            force_mount=True,
            on_escape_key_down=rx.console_log("escape"),
        ),
        on_open_change=rx.console_log("changed"),
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
                "children": [{"contents": '"Delete"'}],
            },
            {
                "name": '"dialog"',
                "props": [
                    '"aria-describedby":"rx-dialog-1-describedby"',
                    '"aria-labelledby":"rx-dialog-1-labelledby"',
                    "className:sx_bf687cb34b_c",
                    '"data-rx-keep":"outside"',
                    '"data-rx-popup":""',
                    'id:"rx-dialog-1"',
                    "onCancel:dialogEvent",
                    "onClose:dialogEvent",
                    'ref:((dialog) => dialogSync(dialog, null, ({ open: ((_ev_0) => (addEvents([(ReflexEvent("_call_function", ({ ["function"] : (() => (console?.["log"]("changed"))), ["callback"] : null }), ({  })))], [_ev_0], ({  })))), escape: ((...args) => (addEvents([(ReflexEvent("_call_function", ({ ["function"] : (() => (console?.["log"]("escape"))), ["callback"] : null }), ({  })))], args, ({  })))) })))',
                    'role:"alertdialog"',
                ],
                "children": [
                    {
                        "name": '"div"',
                        "props": [
                            "className:sx_18e4ad36e3_c",
                            '"data-rx-dialog-pad":""',
                        ],
                        "children": [
                            {
                                "name": '"div"',
                                "props": ["className:sx_849936ac28_c"],
                                "children": [
                                    {
                                        "name": '"h1"',
                                        "props": [
                                            "className:sx_29271ef72f_c",
                                            'id:"rx-dialog-1-labelledby"',
                                        ],
                                        "children": [{"contents": '"Delete the file"'}],
                                    },
                                    {
                                        "name": '"p"',
                                        "props": [
                                            "className:sx_9b5373509f_c",
                                            'id:"rx-dialog-1-describedby"',
                                        ],
                                        "children": [
                                            {"contents": '"It cannot be brought back."'}
                                        ],
                                    },
                                    {
                                        "name": '"button"',
                                        "props": [
                                            'command:"close"',
                                            'commandfor:"rx-dialog-1"',
                                            '"data-rx-dialog-close":""',
                                        ],
                                        "children": [{"contents": '"Delete it"'}],
                                    },
                                    {
                                        "name": '"button"',
                                        "props": [
                                            'command:"close"',
                                            'commandfor:"rx-dialog-1"',
                                            '"data-rx-dialog-close":"cancel"',
                                        ],
                                        "children": [{"contents": '"Keep it"'}],
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
            "backgroundColor": {
                "default": "transparent",
                "::backdrop": "transparent",
                "::before": "var(--color-overlay)",
            },
            "color": "inherit",
            "maxWidth": "none",
            "maxHeight": "none",
            "outlineStyle": "none",
            "transitionProperty": {
                "default": "display, overlay",
                "::before": "opacity",
            },
            "transitionDuration": {
                "default": "0s",
                "@media (prefers-reduced-motion: no-preference)": "var(--rx-dialog-duration)",
                "::before": {
                    "default": "0s",
                    "@media (prefers-reduced-motion: no-preference)": "var(--rx-dialog-duration)",
                },
            },
            "--rx-dialog-shown": {"default": 0, "[open]": 1},
            "position": {"default": "fixed", "::before": "fixed"},
            "top": {"default": "0", "::before": "0"},
            "right": {"default": "0", "::before": "0"},
            "bottom": {"default": "0", "::before": "0"},
            "left": {"default": "0", "::before": "0"},
            "width": "100%",
            "height": "100%",
            "display": {"default": "none", "[open]": "flex"},
            "overflowX": "auto",
            "overflowY": "auto",
            "--rx-dialog-gone": {
                "default": "translateY(5px) scale(0.99)",
                "[open]": "none",
            },
            "--rx-dialog-duration": {"default": "160ms", "[open]": "200ms"},
            "content": {"::before": "''"},
            "opacity": {
                "::before": {
                    "default": 0,
                    "[open]": {"default": 1, "@starting-style": 0},
                }
            },
            "transitionTimingFunction": {"::before": "cubic-bezier(0.16, 1, 0.3, 1)"},
        },
        {
            "flexGrow": 1,
            "marginTop": "auto",
            "marginRight": "auto",
            "marginBottom": "auto",
            "marginLeft": "auto",
            "paddingTop": "var(--space-6)",
            "paddingBottom": "max(var(--space-6), 6vh)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
        },
        {
            "marginTop": "auto",
            "marginRight": "auto",
            "marginBottom": "auto",
            "marginLeft": "auto",
            "width": "100%",
            "maxWidth": "600px",
            "zIndex": 1,
            "position": "relative",
            "boxSizing": "border-box",
            "overflowX": "auto",
            "overflowY": "auto",
            "--inset-padding-top": "var(--dialog-content-padding)",
            "--inset-padding-right": "var(--dialog-content-padding)",
            "--inset-padding-bottom": "var(--dialog-content-padding)",
            "--inset-padding-left": "var(--dialog-content-padding)",
            "padding": "var(--dialog-content-padding)",
            "backgroundColor": "var(--color-panel-solid)",
            "boxShadow": "var(--shadow-6)",
            "outlineStyle": "none",
            "opacity": {"default": "var(--rx-dialog-shown)", "@starting-style": 0},
            "transform": {
                "default": "var(--rx-dialog-gone)",
                "@starting-style": "translateY(5px) scale(0.97)",
            },
            "transitionProperty": "opacity, transform",
            "transitionDuration": {
                "default": "0s",
                "@media (prefers-reduced-motion: no-preference)": "calc(100ms + var(--rx-dialog-shown) * 100ms)",
            },
            "transitionTimingFunction": "cubic-bezier(0.16, 1, 0.3, 1)",
            "--dialog-content-padding": "var(--space-3)",
            "borderTopLeftRadius": "var(--radius-4)",
            "borderTopRightRadius": "var(--radius-4)",
            "borderBottomRightRadius": "var(--radius-4)",
            "borderBottomLeftRadius": "var(--radius-4)",
        },
        {
            "--leading-trim-start": "var(--heading-leading-trim-start)",
            "--leading-trim-end": "var(--heading-leading-trim-end)",
            "fontFamily": "var(--heading-font-family)",
            "fontStyle": "var(--heading-font-style)",
            "fontWeight": "var(--font-weight-bold)",
            "lineHeight": "var(--line-height)",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": {
                "default": "var(--space-3)",
                "::before": "calc(var(--leading-trim-start, var(--default-leading-trim-start)) - var(--line-height, calc(1em * var(--default-line-height))) / 2)",
            },
            "marginLeft": "0",
            "fontSize": "calc(var(--font-size-5) * var(--heading-font-size-adjust))",
            "--line-height": "var(--heading-line-height-5)",
            "letterSpacing": "calc(var(--letter-spacing-5) + var(--heading-letter-spacing))",
            "content": {"::before": "''", "::after": "none"},
            "display": {"::before": "table"},
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--font-size-3)",
            "--line-height": "var(--line-height-3)",
            "--letter-spacing": "var(--letter-spacing-3)",
        },
        {},
        {},
    ]
