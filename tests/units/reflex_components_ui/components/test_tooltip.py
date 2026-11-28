"""Tests for reflex_components_ui.components.tooltip."""

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


def test_tooltip(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A tooltip is its child, which it describes, then a popover with its text, which a script opens under the pointer and with the focus."""
    component = rx.ui.tooltip(
        rx.el.button("Save", id="save"),
        content="Saves the file",
        side="bottom",
        align="start",
        side_offset=6,
        delay_duration=0,
        disable_hoverable_content=True,
        default_open=True,
        aria_label="Save",
        max_width="200px",
    )
    assert component.render() == {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "name": '"button"',
                "props": [
                    '"aria-describedby":"rx-tooltip-1"',
                    '"data-rx-hover":"rx-tooltip-1"',
                    '"data-state":"closed"',
                    'id:"save"',
                    "onBlur:hoverEvent",
                    "onFocus:hoverEvent",
                    "onPointerDown:hoverEvent",
                    "onPointerEnter:hoverEvent",
                    "onPointerLeave:hoverEvent",
                    "ref:ref_save",
                ],
                "children": [{"contents": '"Save"'}],
            },
            {
                "name": '"div"',
                "props": [
                    '"aria-label":"Save"',
                    "className:sx_6a0d355fdc_c",
                    '"data-close-delay":0',
                    '"data-default-open":true',
                    '"data-open-delay":0',
                    '"data-rx-popup":""',
                    'id:"rx-tooltip-1"',
                    "onBlur:hoverEvent",
                    "onPointerEnter:hoverEvent",
                    "onPointerLeave:hoverEvent",
                    'popover:"manual"',
                    "ref:((popup) => hoverSync(popup, null))",
                    'role:"tooltip"',
                ],
                "children": [
                    {
                        "name": '"p"',
                        "props": ["className:sx_7f6c9bc5c4_c"],
                        "children": [{"contents": '"Saves the file"'}],
                    }
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {},
        {
            "position": "fixed",
            "top": "auto",
            "right": "auto",
            "bottom": "auto",
            "left": "auto",
            "marginTop": "var(--rx-popup-offset, 9px)",
            "marginRight": "0",
            "marginBottom": "var(--rx-popup-offset, 9px)",
            "marginLeft": "var(--rx-popup-shift, 0px)",
            "paddingTop": "var(--space-1)",
            "paddingRight": "var(--space-2)",
            "paddingBottom": "var(--space-1)",
            "paddingLeft": "var(--space-2)",
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
            "maxWidth": "200px",
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
                    "default": "0s",
                    ":popover-open": "140ms",
                },
            },
            "transitionTimingFunction": "cubic-bezier(0.16, 1, 0.3, 1)",
            "overflowX": "visible",
            "overflowY": "visible",
            "backgroundColor": "var(--gray-12)",
            "borderTopLeftRadius": "var(--radius-2)",
            "borderTopRightRadius": "var(--radius-2)",
            "borderBottomRightRadius": "var(--radius-2)",
            "borderBottomLeftRadius": "var(--radius-2)",
            "pointerEvents": "none",
            "positionArea": "bottom span-right",
            "maxHeight": "calc(100% - var(--rx-popup-offset, 9px) - 10px)",
            "--rx-popup-from": "translateY(-4px) scale(0.97)",
            "transformOrigin": "top left",
            "--rx-popup-offset": "11px",
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--font-size-1)",
            "--line-height": "var(--line-height-1)",
            "--letter-spacing": "var(--letter-spacing-1)",
            "color": "var(--gray-1)",
            "userSelect": "none",
            "cursor": "default",
        },
    ]


class TooltipState(rx.State):
    """What a tooltip is bound to."""

    shown: bool = False
    still: bool = False

    @rx.event
    def set_shown(self, shown: bool):
        """Follow the tooltip.

        Args:
            shown: Whether it is open.
        """
        self.shown = shown


def test_tooltip_bound_to_state(ui_plugin: UIPlugin):
    """A tooltip bound to state hands its script its state and what it does when it is asked to open or close."""
    name = TooltipState.get_full_name()
    component = rx.ui.tooltip(
        rx.el.button("Save"),
        content="Saves the file",
        open=TooltipState.shown,
        on_open_change=TooltipState.set_shown,
        disable_hoverable_content=TooltipState.still,
    )
    trigger, popup = component.render()["children"]
    assert trigger["props"] == [
        '"aria-describedby":"rx-tooltip-1"',
        '"data-rx-hover":"rx-tooltip-1"',
        '"data-state":"closed"',
        "onBlur:hoverEvent",
        "onFocus:hoverEvent",
        "onPointerDown:hoverEvent",
        "onPointerEnter:hoverEvent",
        "onPointerLeave:hoverEvent",
    ]
    assert popup["props"] == [
        f'className:sx_7d0b44bf5e_c + " " + (sx_7d0b44bf5e_0[{TooltipState.still!s}] ?? "")',
        f'"data-close-delay":({TooltipState.still!s} ? 0 : 100)',
        '"data-open-delay":200',
        '"data-rx-popup":""',
        'id:"rx-tooltip-1"',
        "onBlur:hoverEvent",
        "onPointerEnter:hoverEvent",
        "onPointerLeave:hoverEvent",
        'popover:"manual"',
        (
            f"ref:((popup) => hoverSync(popup, {TooltipState.shown!s}, ({{ open: "
            f'((_ev_0) => (addEvents([(ReflexEvent("{name}.set_shown", '
            '({ ["shown"] : _ev_0 }), ({  })))], [_ev_0], ({  })))) })))'
        ),
        'role:"tooltip"',
    ]


def test_tooltip_imports_its_script(ui_plugin: UIPlugin):
    """A page with a tooltip loads the script of the popups that open under the pointer, and no other."""
    component = rx.ui.tooltip(rx.el.button("Save"), content="Saves the file")
    imports = component._get_all_imports()
    assert {
        module: names for module, names in imports.items() if "behaviors" in module
    } == {
        "$/reflex-ui/behaviors/hover.js": [
            ImportVar(tag="hoverEvent"),
            ImportVar(tag="hoverSync"),
        ],
    }


def test_tooltip_needs_an_element_to_describe(ui_plugin: UIPlugin):
    """A tooltip on anything but one element fails with the name of the component."""
    with pytest.raises(StyleError) as error:
        rx.ui.tooltip("Save", content="Saves the file")
    assert str(error.value) == (
        "rx.ui.tooltip_trigger: it is rendered as its child, so it needs exactly "
        "one child that is an element, such as a button."
    )
