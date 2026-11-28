"""Tests for reflex_components_ui.components.popover."""

import itertools
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.components import _popup
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


@pytest.fixture(autouse=True)
def ids(monkeypatch: pytest.MonkeyPatch):
    """Number the popups of each test from one."""
    monkeypatch.setattr(_popup, "_ids", itertools.count(1))


def test_popover(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A popover is a native popover right after its trigger, which the browser opens it from; the root is nothing in the page, and the close button closes the popover without a script."""
    component = rx.ui.popover.root(
        rx.ui.popover.trigger(rx.el.button("Open", id="open")),
        rx.ui.popover.content(
            "Inside",
            rx.ui.popover.close(rx.el.button("Close")),
            size="1",
            side="top",
            align="end",
            side_offset=4,
            align_offset=2,
            collision_padding=20,
            avoid_collisions=False,
            max_width="300px",
        ),
        default_open=True,
        modal=True,
    )
    assert component.render() == {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "name": '"button"',
                "props": [
                    '"aria-controls":"rx-popover-1"',
                    '"aria-expanded":false',
                    '"aria-haspopup":"dialog"',
                    '"data-state":"closed"',
                    'id:"open"',
                    'popovertarget:"rx-popover-1"',
                    "ref:ref_open",
                ],
                "children": [{"contents": '"Open"'}],
            },
            {
                "name": '"div"',
                "props": [
                    "className:sx_1ea534d980_c",
                    '"data-default-open":true',
                    '"data-rx-popup":""',
                    'id:"rx-popover-1"',
                    "onBlur:popupEvent",
                    "onClick:popupEvent",
                    "onKeyDown:popupEvent",
                    "onToggle:popupEvent",
                    'popover:"auto"',
                    "ref:((popup) => popupSync(popup, null))",
                    'role:"dialog"',
                    "tabIndex:-1",
                ],
                "children": [
                    {"contents": '"Inside"'},
                    {
                        "name": '"button"',
                        "props": [
                            'popovertarget:"rx-popover-1"',
                            'popovertargetaction:"hide"',
                        ],
                        "children": [{"contents": '"Close"'}],
                    },
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {},
        {},
        {
            "position": "fixed",
            "top": "auto",
            "right": "auto",
            "bottom": "auto",
            "left": "auto",
            "marginTop": "var(--rx-popup-offset, 8px)",
            "marginRight": "var(--rx-popup-shift, 0px)",
            "marginBottom": "var(--rx-popup-offset, 8px)",
            "marginLeft": "0",
            "padding": "var(--popover-content-padding)",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "boxSizing": "border-box",
            "width": "max-content",
            "height": "auto",
            "maxWidth": "300px",
            "positionTryFallbacks": "flip-block, flip-inline",
            "opacity": {
                "default": 0,
                ":popover-open": {"default": 1, "@starting-style": 0},
            },
            "transform": {
                "default": "var(--rx-popup-from)",
                ":popover-open": {
                    "default": "none",
                    "@starting-style": "var(--rx-popup-from)",
                },
            },
            "transitionProperty": "opacity, transform, display, overlay",
            "transitionDuration": {
                "default": "0s",
                "@media (prefers-reduced-motion: no-preference)": {
                    "default": "100ms",
                    ":popover-open": "160ms",
                },
            },
            "transitionTimingFunction": "cubic-bezier(0.16, 1, 0.3, 1)",
            "color": "inherit",
            "backgroundColor": "var(--color-panel-solid)",
            "boxShadow": "var(--shadow-5)",
            "minWidth": "anchor-size(width)",
            "outlineStyle": "none",
            "overflowX": "auto",
            "overflowY": "auto",
            "--inset-padding-top": "var(--popover-content-padding)",
            "--inset-padding-right": "var(--popover-content-padding)",
            "--inset-padding-bottom": "var(--popover-content-padding)",
            "--inset-padding-left": "var(--popover-content-padding)",
            "--popover-content-padding": "var(--space-3)",
            "borderTopLeftRadius": "var(--radius-4)",
            "borderTopRightRadius": "var(--radius-4)",
            "borderBottomRightRadius": "var(--radius-4)",
            "borderBottomLeftRadius": "var(--radius-4)",
            "positionArea": "top span-left",
            "maxHeight": "calc(100% - var(--rx-popup-offset, 8px) - 10px)",
            "--rx-popup-from": "translateY(4px) scale(0.97)",
            "transformOrigin": "bottom right",
            "--rx-popup-offset": "4px",
            "--rx-popup-shift": "2px",
        },
        {},
    ]


def test_popover_with_an_id(ui_plugin: UIPlugin):
    """A popover that is given an id is named by it, and one outside a root is a popover nothing opens."""
    component = rx.el.div(
        rx.ui.popover.root(
            rx.ui.popover.trigger(rx.el.button("Open")),
            rx.ui.popover.content("Inside", id="panel"),
        ),
        rx.ui.popover.content("Alone"),
    )
    assert component.render() == {
        "name": '"div"',
        "props": [],
        "children": [
            {
                "name": "Fragment",
                "props": [],
                "children": [
                    {
                        "name": '"button"',
                        "props": [
                            '"aria-controls":"panel"',
                            '"aria-expanded":false',
                            '"aria-haspopup":"dialog"',
                            '"data-state":"closed"',
                            'popovertarget:"panel"',
                        ],
                        "children": [{"contents": '"Open"'}],
                    },
                    {
                        "name": '"div"',
                        "props": [
                            "className:sx_10268a09e0_c",
                            '"data-rx-popup":""',
                            'id:"panel"',
                            "onBlur:popupEvent",
                            "onClick:popupEvent",
                            "onKeyDown:popupEvent",
                            "onToggle:popupEvent",
                            'popover:"auto"',
                            "ref:((popup) => popupSync(popup, null))",
                            'role:"dialog"',
                            "tabIndex:-1",
                        ],
                        "children": [{"contents": '"Inside"'}],
                    },
                ],
            },
            {
                "name": '"div"',
                "props": [
                    "className:sx_10268a09e0_c",
                    '"data-rx-popup":""',
                    "onBlur:popupEvent",
                    "onClick:popupEvent",
                    "onKeyDown:popupEvent",
                    "onToggle:popupEvent",
                    'popover:"auto"',
                    "ref:((popup) => popupSync(popup, null))",
                    'role:"dialog"',
                    "tabIndex:-1",
                ],
                "children": [{"contents": '"Alone"'}],
            },
        ],
    }


class PopoverState(rx.State):
    """What a popover is bound to."""

    shown: bool = False
    gap: int = 6

    @rx.event
    def set_shown(self, shown: bool):
        """Follow the popover.

        Args:
            shown: Whether it is open.
        """
        self.shown = shown

    @rx.event
    def note(self):
        """Hear that something happened to the popover."""


def test_popover_bound_to_state(ui_plugin: UIPlugin):
    """A popover bound to state hands its script its state and what it does when it opens, closes or is dismissed, and an offset bound to state is a custom property."""
    name = PopoverState.get_full_name()
    component = rx.ui.popover.root(
        rx.ui.popover.trigger(rx.el.button("Open")),
        rx.ui.popover.content(
            "x",
            side_offset=PopoverState.gap,
            on_focus_outside=PopoverState.note,
        ),
        open=PopoverState.shown,
        on_open_change=PopoverState.set_shown,
    )
    rendered = component.render()
    assert (rendered["name"], rendered["props"]) == ("Fragment", [])
    on = (
        f'({{ open: ((_ev_0) => (addEvents([(ReflexEvent("{name}.set_shown", '
        '({ ["shown"] : _ev_0 }), ({  })))], [_ev_0], ({  })))), focusOutside: '
        f'((...args) => (addEvents([(ReflexEvent("{name}.note", ({{  }}), '
        "({  })))], args, ({  })))) })"
    )
    assert rendered["children"][1]["props"] == [
        "className:sx_13adaeddb0_c",
        '"data-rx-popup":""',
        'id:"rx-popover-1"',
        f"onBlur:((event) => popupEvent(event, {on}))",
        f"onClick:((event) => popupEvent(event, {on}))",
        f"onKeyDown:((event) => popupEvent(event, {on}))",
        f"onToggle:((event) => popupEvent(event, {on}))",
        'popover:"auto"',
        f"ref:((popup) => popupSync(popup, {PopoverState.shown!s}))",
        'role:"dialog"',
        f'style:({{ "--v0": ((({PopoverState.gap!s}) + "px")) ?? "initial" }})',
        "tabIndex:-1",
    ]


def test_popover_imports_its_script(ui_plugin: UIPlugin):
    """A page with a popover loads the script of a popup, and no other."""
    component = rx.ui.popover.root(
        rx.ui.popover.trigger(rx.el.button("Open")), rx.ui.popover.content("x")
    )
    imports = component._get_all_imports()
    assert {
        module: names for module, names in imports.items() if "behaviors" in module
    } == {
        "$/reflex-ui/behaviors/popup.js": [
            ImportVar(tag="popupSync"),
            ImportVar(tag="popupEvent"),
        ],
    }


@pytest.mark.parametrize(
    ("create", "message"),
    [
        (
            lambda: rx.ui.popover.trigger("Open"),
            (
                "rx.ui.popover_trigger: it is rendered as its child, so it needs exactly "
                "one child that is an element, such as a button."
            ),
        ),
        (
            lambda: rx.ui.popover.content(side="above"),  # pyright: ignore[reportArgumentType]
            (
                'rx.ui.popover_content: unknown side "above". The values are "top", '
                '"right", "bottom", "left".'
            ),
        ),
    ],
)
def test_popover_refuses_what_it_cannot_render(
    ui_plugin: UIPlugin, create: Callable[[], Any], message: str
):
    """A trigger without one element to render as, and a side a popover does not have, fail with the name of the component."""
    with pytest.raises(StyleError) as error:
        create()
    assert str(error.value) == message
