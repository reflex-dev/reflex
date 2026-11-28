"""Tests for reflex_components_ui.components.dialog."""

import itertools
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.components import _dialog
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


@pytest.fixture(autouse=True)
def ids(monkeypatch: pytest.MonkeyPatch):
    """Number the dialogs of each test from one."""
    monkeypatch.setattr(_dialog, "_ids", itertools.count(1))


def test_dialog(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A dialog is a native dialog over the page, around the panel an app styles; its trigger and its close button are their children, which command it; its title and its description name it."""
    component = rx.ui.dialog.root(
        rx.ui.dialog.trigger(rx.el.button("Open", id="open")),
        rx.ui.dialog.content(
            rx.ui.dialog.title("Title"),
            rx.ui.dialog.description("What it is about.", id="about"),
            rx.ui.dialog.close(rx.el.button("Close")),
            size="2",
            max_width="400px",
            id="panel",
        ),
        default_open=True,
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
                    'id:"open"',
                    "ref:ref_open",
                ],
                "children": [{"contents": '"Open"'}],
            },
            {
                "name": '"dialog"',
                "props": [
                    '"aria-describedby":"about"',
                    '"aria-labelledby":"rx-dialog-1-labelledby"',
                    "className:sx_bf687cb34b_c",
                    '"data-default-open":true',
                    '"data-rx-popup":""',
                    'id:"rx-dialog-1"',
                    "onCancel:dialogEvent",
                    "onClose:dialogEvent",
                    "ref:((dialog) => dialogSync(dialog, null, null))",
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
                                "props": [
                                    "className:sx_02cf547cd4_c",
                                    'id:"panel"',
                                    "ref:ref_panel",
                                ],
                                "children": [
                                    {
                                        "name": '"h1"',
                                        "props": [
                                            "className:sx_29271ef72f_c",
                                            'id:"rx-dialog-1-labelledby"',
                                        ],
                                        "children": [{"contents": '"Title"'}],
                                    },
                                    {
                                        "name": '"p"',
                                        "props": [
                                            "className:sx_9b5373509f_c",
                                            'id:"about"',
                                            "ref:ref_about",
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
            "maxWidth": "400px",
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
            "--dialog-content-padding": "var(--space-4)",
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
    ]


def test_dialog_in_a_dialog(ui_plugin: UIPlugin):
    """A dialog inside a dialog is its own: each trigger commands its dialog, and a child that hears a press itself is put in a flex container."""
    component = rx.ui.dialog.root(
        rx.ui.dialog.trigger(rx.el.button("Open", on_click=rx.console_log("pressed"))),
        rx.ui.dialog.content(
            rx.ui.dialog.root(
                rx.ui.dialog.trigger(rx.el.button("Inner")),
                rx.ui.dialog.content("Inside"),
            ),
        ),
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
                "name": '"div"',
                "props": [
                    '"aria-controls":"rx-dialog-2"',
                    '"aria-expanded":false',
                    '"aria-haspopup":"dialog"',
                    "className:sx_78b49527aa_c",
                    'command:"show-modal"',
                    'commandfor:"rx-dialog-2"',
                    '"data-rx-dialog-trigger":""',
                    '"data-state":"closed"',
                ],
                "children": [
                    {
                        "name": '"button"',
                        "props": [
                            'onClick:((_e) => (addEvents([(ReflexEvent("_call_function", ({ ["function"] : (() => (console?.["log"]("pressed"))), ["callback"] : null }), ({  })))], [_e], ({  }))))'
                        ],
                        "children": [{"contents": '"Open"'}],
                    }
                ],
            },
            {
                "name": '"dialog"',
                "props": [
                    "className:sx_bf687cb34b_c",
                    '"data-rx-popup":""',
                    'id:"rx-dialog-2"',
                    "onCancel:dialogEvent",
                    "onClose:dialogEvent",
                    "ref:((dialog) => dialogSync(dialog, null, null))",
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
                                "props": ["className:sx_41c452192b_c"],
                                "children": [
                                    {
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
                                                "children": [{"contents": '"Inner"'}],
                                            },
                                            {
                                                "name": '"dialog"',
                                                "props": [
                                                    "className:sx_bf687cb34b_c",
                                                    '"data-rx-popup":""',
                                                    'id:"rx-dialog-1"',
                                                    "onCancel:dialogEvent",
                                                    "onClose:dialogEvent",
                                                    "ref:((dialog) => dialogSync(dialog, null, null))",
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
                                                                "props": [
                                                                    "className:sx_41c452192b_c"
                                                                ],
                                                                "children": [
                                                                    {
                                                                        "contents": '"Inside"'
                                                                    }
                                                                ],
                                                            }
                                                        ],
                                                    }
                                                ],
                                            },
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ],
    }


def test_dialog_parts_alone(ui_plugin: UIPlugin):
    """The parts of a dialog outside one render without its name."""
    component = rx.el.div(
        rx.ui.dialog.trigger(rx.el.button("Open")),
        rx.ui.dialog.content(
            rx.ui.dialog.title("Title"), rx.ui.dialog.description("About")
        ),
        rx.ui.dialog.close(rx.el.button("Close")),
    )
    assert component.render() == {
        "name": '"div"',
        "props": [],
        "children": [
            {
                "name": '"button"',
                "props": [
                    '"aria-expanded":false',
                    '"aria-haspopup":"dialog"',
                    '"data-rx-dialog-trigger":""',
                    '"data-state":"closed"',
                ],
                "children": [{"contents": '"Open"'}],
            },
            {
                "name": '"dialog"',
                "props": [
                    "className:sx_bf687cb34b_c",
                    '"data-rx-popup":""',
                    "onCancel:dialogEvent",
                    "onClose:dialogEvent",
                    "ref:((dialog) => dialogSync(dialog, null, null))",
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
                                "props": ["className:sx_41c452192b_c"],
                                "children": [
                                    {
                                        "name": '"h1"',
                                        "props": ["className:sx_29271ef72f_c"],
                                        "children": [{"contents": '"Title"'}],
                                    },
                                    {
                                        "name": '"p"',
                                        "props": ["className:sx_9b5373509f_c"],
                                        "children": [{"contents": '"About"'}],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "name": '"button"',
                "props": ['"data-rx-dialog-close":""'],
                "children": [{"contents": '"Close"'}],
            },
        ],
    }


class DialogState(rx.State):
    """What a dialog is bound to."""

    shown: bool = False

    @rx.event
    def set_shown(self, shown: bool):
        """Follow the dialog.

        Args:
            shown: Whether it is open.
        """
        self.shown = shown

    @rx.event
    def note(self):
        """Hear that something happened to the dialog."""


def test_dialog_bound_to_state(ui_plugin: UIPlugin):
    """A dialog bound to state hands its script its state and what it does when it is asked to open or close, and its trigger commands nothing."""
    name = DialogState.get_full_name()
    component = rx.ui.dialog.root(
        rx.ui.dialog.trigger(rx.el.button("Open")),
        rx.ui.dialog.content(
            "x",
            on_escape_key_down=DialogState.note,
            on_interact_outside=DialogState.note,
        ),
        open=DialogState.shown,
        on_open_change=DialogState.set_shown,
    )
    rendered = component.render()
    assert rendered["props"] == [
        "className:sx_71b84cd269_c",
        '"data-rx-dialog-root":""',
        "onClick:dialogClick",
    ]
    trigger, dialog = rendered["children"]
    assert trigger["props"] == [
        '"aria-controls":"rx-dialog-1"',
        '"aria-expanded":false',
        '"aria-haspopup":"dialog"',
        '"data-rx-dialog-trigger":""',
        '"data-state":"closed"',
    ]
    note = (
        f'((...args) => (addEvents([(ReflexEvent("{name}.note", ({{  }}), '
        "({  })))], args, ({  }))))"
    )
    assert dialog["props"] == [
        "className:sx_bf687cb34b_c",
        '"data-rx-popup":""',
        'id:"rx-dialog-1"',
        "onCancel:dialogEvent",
        "onClose:dialogEvent",
        (
            f"ref:((dialog) => dialogSync(dialog, {DialogState.shown!s}, ({{ open: "
            f'((_ev_0) => (addEvents([(ReflexEvent("{name}.set_shown", '
            '({ ["shown"] : _ev_0 }), ({  })))], [_ev_0], ({  })))), '
            f"escape: {note}, interact: {note} }})))"
        ),
    ]


def test_dialog_imports_its_script(ui_plugin: UIPlugin):
    """A page with a dialog loads the script of a dialog, and no other."""
    component = rx.ui.dialog.root(
        rx.ui.dialog.trigger(rx.el.button("Open")), rx.ui.dialog.content("x")
    )
    imports = component._get_all_imports()
    assert {
        module: names for module, names in imports.items() if "behaviors" in module
    } == {
        "$/reflex-ui/behaviors/dialog.js": [
            ImportVar(tag="dialogClick"),
            ImportVar(tag="dialogSync"),
            ImportVar(tag="dialogEvent"),
        ],
    }


@pytest.mark.parametrize(
    ("create", "message"),
    [
        (
            lambda: rx.ui.dialog.trigger("Open"),
            (
                "rx.ui.dialog_trigger: it is rendered as its child, so it needs exactly "
                "one child that is an element, such as a button."
            ),
        ),
        (
            lambda: rx.ui.dialog.close(rx.el.button("a"), rx.el.button("b")),
            (
                "rx.ui.dialog_close: it is rendered as its child, so it needs exactly "
                "one child that is an element, such as a button."
            ),
        ),
        (
            lambda: rx.ui.dialog.content(size="9"),  # pyright: ignore[reportArgumentType]
            'rx.ui.dialog_content: unknown size "9". The values are "1", "2", "3", "4".',
        ),
    ],
)
def test_dialog_refuses_what_it_cannot_render(
    ui_plugin: UIPlugin, create: Callable[[], Any], message: str
):
    """A trigger without one element to render as, and a size a dialog does not have, fail with the name of the component."""
    with pytest.raises(StyleError) as error:
        create()
    assert str(error.value) == message
