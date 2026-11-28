"""Tests for reflex_components_ui.components.select."""

import itertools
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.components import select as select_module
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


@pytest.fixture(autouse=True)
def ids(monkeypatch: pytest.MonkeyPatch):
    """Number the popups and the labels of each test from one."""
    monkeypatch.setattr(select_module, "_ids", itertools.count(1))


class SelectState(rx.State):
    """What a select is bound to."""

    fruit: str = "apple"
    fruits: list[str] = ["apple", "pear"]
    is_open: bool = False
    offset: int = 6

    @rx.event
    def set_fruit(self, fruit: str):
        """Follow the select.

        Args:
            fruit: The chosen value.
        """
        self.fruit = fruit

    @rx.event
    def set_is_open(self, is_open: bool):
        """Follow the list of the select.

        Args:
            is_open: Whether it is open.
        """
        self.is_open = is_open

    @rx.event
    def closed(self):
        """Hear that the list closed."""


def test_select(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A select is a button that opens a popover of options, and an input that holds its value; the root hands its size to both and its state to the input."""
    component = rx.ui.select.root(
        rx.ui.select.trigger(
            placeholder="Pick",
            variant="classic",
            radius="full",
            color_scheme="ruby",
            id="pick",
            margin="1px",
        ),
        rx.ui.select.content(
            rx.ui.select.group(
                rx.ui.select.label("Fruits"),
                rx.ui.select.item("Apple", value="apple"),
                rx.ui.select.item("Pear", value="pear", disabled=True, id="pear"),
            ),
            rx.ui.select.separator(),
            rx.ui.select.item(rx.el.b("None"), value="none"),
            variant="soft",
            high_contrast=True,
            color_scheme="jade",
            side="top",
            align="end",
            side_offset=8,
            align_offset=2,
            position="popper",
            z_index="5",
        ),
        default_value="pear",
        name="fruit",
        required=True,
        disabled=True,
        size="3",
        default_open=True,
        id="fruit",
    )
    assert component.render() == {
        "name": '"span"',
        "props": [
            "className:sx_71b84cd269_c",
            '"data-default-open":true',
            '"data-rx-select":""',
            'id:"fruit"',
            "onClick:selectClick",
            "onKeyDown:selectKeyDown",
            "onPointerMove:selectPointerMove",
            "ref:ref_fruit",
        ],
        "children": [
            {
                "name": '"button"',
                "props": [
                    '"aria-autocomplete":"none"',
                    '"aria-controls":"rx-select-2"',
                    '"aria-expanded":"false"',
                    '"aria-haspopup":"listbox"',
                    'className:sx_0f680e2b85_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_4c7cd6a7ce',
                    '"data-state":"closed"',
                    "disabled:true",
                    'id:"pick"',
                    'popovertarget:"rx-select-2"',
                    "ref:ref_pick",
                    'role:"combobox"',
                    'type:"button"',
                ],
                "children": [
                    {
                        "name": '"span"',
                        "props": [
                            "className:sx_94480a599d_c",
                            '"data-placeholder":"Pick"',
                            '"data-rx-select-shown":""',
                        ],
                        "children": [{"contents": '"Pear"'}],
                    },
                    {
                        "name": '"svg"',
                        "props": [
                            '"aria-hidden":true',
                            "className:sx_9779d39f10_c",
                            'fill:"currentcolor"',
                            'height:"9"',
                            'viewBox:"0 0 9 9"',
                            'width:"9"',
                            'xmlns:"http://www.w3.org/2000/svg"',
                        ],
                        "children": [
                            {
                                "name": '"path"',
                                "props": [
                                    'd:"M0.135232 3.15803C0.324102 2.95657 0.640521 2.94637 0.841971 3.13523L4.5 6.56464L8.158 3.13523C8.3595 2.94637 8.6759 2.95657 8.8648 3.15803C9.0536 3.35949 9.0434 3.67591 8.842 3.86477L4.84197 7.6148C4.64964 7.7951 4.35036 7.7951 4.15803 7.6148L0.158031 3.86477C-0.0434285 3.67591 -0.0536285 3.35949 0.135232 3.15803Z"'
                                ],
                                "children": [],
                            }
                        ],
                    },
                ],
            },
            {
                "name": '"div"',
                "props": [
                    'className:sx_222d3d03d6_c + " " + reflexUIClasses_f97593a337',
                    '"data-rx-popup":""',
                    'id:"rx-select-2"',
                    "onToggle:selectToggle",
                    'popover:"auto"',
                    'role:"listbox"',
                    "tabIndex:-1",
                ],
                "children": [
                    {
                        "name": '"div"',
                        "props": [
                            '"aria-labelledby":"rx-select-label-1"',
                            'role:"group"',
                        ],
                        "children": [
                            {
                                "name": '"div"',
                                "props": [
                                    "className:sx_4c825b9931_c",
                                    '"data-rx-select-label":""',
                                    'id:"rx-select-label-1"',
                                ],
                                "children": [{"contents": '"Fruits"'}],
                            },
                            {
                                "name": '"div"',
                                "props": [
                                    '"aria-selected":"false"',
                                    "className:sx_afbb711e7e_c",
                                    '"data-value":"apple"',
                                    'role:"option"',
                                    "tabIndex:-1",
                                ],
                                "children": [
                                    {
                                        "name": '"span"',
                                        "props": ["className:sx_9209c0ff85_c"],
                                        "children": [
                                            {
                                                "name": '"svg"',
                                                "props": [
                                                    '"aria-hidden":true',
                                                    "className:sx_26fb6ce487_c",
                                                    'fill:"currentcolor"',
                                                    'height:"9"',
                                                    'viewBox:"0 0 9 9"',
                                                    'width:"9"',
                                                    'xmlns:"http://www.w3.org/2000/svg"',
                                                ],
                                                "children": [
                                                    {
                                                        "name": '"path"',
                                                        "props": [
                                                            'clipRule:"evenodd"',
                                                            'd:"M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z"',
                                                            'fillRule:"evenodd"',
                                                        ],
                                                        "children": [],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    {
                                        "name": '"span"',
                                        "props": ['"data-rx-select-text":""'],
                                        "children": [{"contents": '"Apple"'}],
                                    },
                                ],
                            },
                            {
                                "name": '"div"',
                                "props": [
                                    '"aria-disabled":true',
                                    '"aria-selected":"true"',
                                    "className:sx_afbb711e7e_c",
                                    '"data-value":"pear"',
                                    'id:"pear"',
                                    "ref:ref_pear",
                                    'role:"option"',
                                    "tabIndex:-1",
                                ],
                                "children": [
                                    {
                                        "name": '"span"',
                                        "props": ["className:sx_9209c0ff85_c"],
                                        "children": [
                                            {
                                                "name": '"svg"',
                                                "props": [
                                                    '"aria-hidden":true',
                                                    "className:sx_26fb6ce487_c",
                                                    'fill:"currentcolor"',
                                                    'height:"9"',
                                                    'viewBox:"0 0 9 9"',
                                                    'width:"9"',
                                                    'xmlns:"http://www.w3.org/2000/svg"',
                                                ],
                                                "children": [
                                                    {
                                                        "name": '"path"',
                                                        "props": [
                                                            'clipRule:"evenodd"',
                                                            'd:"M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z"',
                                                            'fillRule:"evenodd"',
                                                        ],
                                                        "children": [],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    {
                                        "name": '"span"',
                                        "props": ['"data-rx-select-text":""'],
                                        "children": [{"contents": '"Pear"'}],
                                    },
                                ],
                            },
                        ],
                    },
                    {
                        "name": '"div"',
                        "props": ['"aria-hidden":true', "className:sx_2d671c061b_c"],
                        "children": [],
                    },
                    {
                        "name": '"div"',
                        "props": [
                            '"aria-selected":"false"',
                            "className:sx_afbb711e7e_c",
                            '"data-value":"none"',
                            'role:"option"',
                            "tabIndex:-1",
                        ],
                        "children": [
                            {
                                "name": '"span"',
                                "props": ["className:sx_9209c0ff85_c"],
                                "children": [
                                    {
                                        "name": '"svg"',
                                        "props": [
                                            '"aria-hidden":true',
                                            "className:sx_26fb6ce487_c",
                                            'fill:"currentcolor"',
                                            'height:"9"',
                                            'viewBox:"0 0 9 9"',
                                            'width:"9"',
                                            'xmlns:"http://www.w3.org/2000/svg"',
                                        ],
                                        "children": [
                                            {
                                                "name": '"path"',
                                                "props": [
                                                    'clipRule:"evenodd"',
                                                    'd:"M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z"',
                                                    'fillRule:"evenodd"',
                                                ],
                                                "children": [],
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "name": '"span"',
                                "props": ['"data-rx-select-text":""'],
                                "children": [
                                    {
                                        "name": '"b"',
                                        "props": [],
                                        "children": [{"contents": '"None"'}],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "name": '"input"',
                "props": [
                    '"aria-hidden":true',
                    "className:sx_b72d7382fd_c",
                    '"data-rx-select-value":""',
                    'defaultValue:"pear"',
                    "disabled:true",
                    'name:"fruit"',
                    "onFocus:selectFocus",
                    "ref:((holder) => syncSelect(holder, null, null))",
                    "required:true",
                    "tabIndex:-1",
                ],
                "children": [],
            },
        ],
    }
    assert declared_styles(component) == [
        {"display": "contents"},
        {
            "appearance": "none",
            "marginTop": "1px",
            "marginRight": "1px",
            "marginBottom": "1px",
            "marginLeft": "1px",
            "paddingTop": "0",
            "paddingRight": "var(--space-4)",
            "paddingBottom": "0",
            "paddingLeft": "var(--space-4)",
            "borderTopWidth": {"default": "0", "::before": "2px"},
            "borderRightWidth": {"default": "0", "::before": "2px"},
            "borderBottomWidth": {"default": "0", "::before": "2px"},
            "borderLeftWidth": {"default": "0", "::before": "2px"},
            "borderTopStyle": {"default": "none", "::before": "solid"},
            "borderRightStyle": {"default": "none", "::before": "solid"},
            "borderBottomStyle": {"default": "none", "::before": "solid"},
            "borderLeftStyle": {"default": "none", "::before": "solid"},
            "backgroundColor": {
                "default": "transparent",
                ":disabled": "var(--gray-2)",
                "::before": {":disabled": "var(--gray-a2)"},
            },
            "backgroundImage": {
                "default": "linear-gradient(var(--gray-2), var(--gray-1))",
                ":disabled": "none",
                "::before": {
                    "default": "linear-gradient(var(--black-a1) -20%, transparent, var(--white-a1) 130%), linear-gradient(var(--color-surface), transparent)",
                    "@media (hover: hover)": {
                        ":hover:not(:disabled)": "linear-gradient(var(--black-a1) -15%, transparent, var(--white-a1) 120%), linear-gradient(var(--gray-2), var(--gray-1))"
                    },
                    ":is([data-state='open'], :has(+ :popover-open)):not(:disabled)": "linear-gradient(var(--black-a1) -15%, transparent, var(--white-a1) 120%), linear-gradient(var(--gray-2), var(--gray-1))",
                    ":disabled": "linear-gradient(var(--black-a1) -20%, transparent, var(--white-a1))",
                },
            },
            "textTransform": "inherit",
            "textIndent": "initial",
            "wordSpacing": "inherit",
            "cursor": {
                "default": "var(--cursor-button)",
                ":disabled": "var(--cursor-disabled)",
            },
            "WebkitTapHighlightColor": "transparent",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "flexShrink": 0,
            "userSelect": "none",
            "verticalAlign": "top",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "outlineStyle": {"default": "none", ":focus-visible": "solid"},
            "outlineWidth": {"default": "medium", ":focus-visible": "2px"},
            "outlineColor": {
                "default": "currentcolor",
                ":focus-visible": "var(--focus-8)",
            },
            "outlineOffset": {"default": "0", ":focus-visible": "-1px"},
            "--rx-select-icon-color": {":disabled": "var(--gray-a9)"},
            "--select-trigger-height": "var(--space-7)",
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
            "fontSize": "var(--font-size-3)",
            "lineHeight": "var(--line-height-3)",
            "letterSpacing": "var(--letter-spacing-3)",
            "borderRadius": "max(var(--radius-3), var(--radius-full))",
            "boxSizing": "border-box",
            "height": "var(--select-trigger-height)",
            "--rx-select-shown-color": {"[data-placeholder]": "var(--gray-a10)"},
            "color": {"default": "var(--gray-12)", ":disabled": "var(--gray-a11)"},
            "boxShadow": {
                "default": "var(--rx-if-light, inset 0 0 0 1px var(--gray-a5), inset 0 2px 1px var(--white-a11), inset 0 -2px 1px var(--gray-a4)) var(--rx-if-dark, inset 0 0 0 1px var(--white-a4), inset 0 1px 1px var(--white-a4), inset 0 -1px 1px var(--black-a9))",
                "@media (hover: hover)": {
                    ":hover:not(:disabled)": "inset 0 0 0 1px var(--gray-a3), var(--rx-if-light, inset 0 0 0 1px var(--gray-a5), inset 0 2px 1px var(--white-a11), inset 0 -2px 1px var(--gray-a4)) var(--rx-if-dark, inset 0 0 0 1px var(--white-a4), inset 0 1px 1px var(--white-a4), inset 0 -1px 1px var(--black-a9))"
                },
                ":is([data-state='open'], :has(+ :popover-open)):not(:disabled)": "inset 0 0 0 1px var(--gray-a3), var(--rx-if-light, inset 0 0 0 1px var(--gray-a5), inset 0 2px 1px var(--white-a11), inset 0 -2px 1px var(--gray-a4)) var(--rx-if-dark, inset 0 0 0 1px var(--white-a4), inset 0 1px 1px var(--white-a4), inset 0 -1px 1px var(--black-a9))",
                ":disabled": "var(--rx-if-light, inset 0 0 0 1px var(--gray-a4), inset 0 -2px 1px var(--gray-a3), inset 0 4px 2px -2px var(--white-a9), inset 0 2px 1px -1px var(--white-a9)) var(--rx-if-dark, inset 0 0 0 1px var(--gray-a5), inset 0 4px 2px -2px var(--gray-a2), inset 0 1px 1px var(--gray-a5), inset 0 -1px 1px var(--black-a3), inset 0 0 0 1px var(--gray-a2))",
            },
            "position": {"default": "relative", "::before": "absolute"},
            "zIndex": {"default": 0, "::before": -1},
            "content": {"::before": "''"},
            "top": {"::before": "0"},
            "right": {"::before": "0"},
            "bottom": {"::before": "0"},
            "left": {"::before": "0"},
            "borderTopColor": {"::before": "transparent"},
            "borderRightColor": {"::before": "transparent"},
            "borderBottomColor": {"::before": "transparent"},
            "borderLeftColor": {"::before": "transparent"},
            "backgroundClip": {"::before": "content-box"},
            "borderTopLeftRadius": {"::before": "inherit"},
            "borderTopRightRadius": {"::before": "inherit"},
            "borderBottomRightRadius": {"::before": "inherit"},
            "borderBottomLeftRadius": {"::before": "inherit"},
            "pointerEvents": {"::before": "none"},
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "textOverflow": "ellipsis",
            "whiteSpace": "nowrap",
            "color": "var(--rx-select-shown-color, inherit)",
            "opacity": "var(--rx-select-shown-opacity, 1)",
        },
        {
            "flexShrink": 0,
            "color": "var(--rx-select-icon-color, inherit)",
            "opacity": 0.9,
            "width": "11px",
            "height": "11px",
        },
        {
            "position": "fixed",
            "top": "auto",
            "right": "auto",
            "bottom": "auto",
            "left": "auto",
            "marginTop": "var(--rx-popup-offset, 4px)",
            "marginRight": "var(--rx-popup-shift, 0px)",
            "marginBottom": "var(--rx-popup-offset, 4px)",
            "marginLeft": "0",
            "padding": "var(--select-content-padding)",
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
            "maxWidth": "calc(100vw - 10px * 2)",
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
            "color": "var(--gray-12)",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "backgroundColor": "var(--color-panel-solid)",
            "boxShadow": "var(--shadow-5)",
            "minWidth": "anchor-size(width)",
            "outlineStyle": "none",
            "overflowY": "auto",
            "scrollbarWidth": "thin",
            "scrollbarColor": "var(--gray-a8) transparent",
            "--select-content-padding": "var(--space-2)",
            "--select-item-height": "var(--space-6)",
            "--select-item-indicator-width": "var(--space-5)",
            "--select-separator-margin-right": "var(--space-3)",
            "borderTopLeftRadius": "var(--radius-4)",
            "borderTopRightRadius": "var(--radius-4)",
            "borderBottomRightRadius": "var(--radius-4)",
            "borderBottomLeftRadius": "var(--radius-4)",
            "--rx-select-font-size": "var(--font-size-3)",
            "--rx-select-line-height": "var(--line-height-2)",
            "--rx-select-letter-spacing": "var(--letter-spacing-3)",
            "--rx-select-label-font-size": "var(--font-size-2)",
            "--rx-select-label-letter-spacing": "var(--letter-spacing-2)",
            "--rx-select-item-radius": "var(--radius-2)",
            "--rx-select-check-size": "calc(10px * var(--scaling))",
            "--rx-select-highlight": "var(--accent-a4)",
            "positionArea": "top span-left",
            "maxHeight": "calc(100% - var(--rx-popup-offset, 4px) - 10px)",
            "--rx-popup-from": "translateY(4px) scale(0.97)",
            "transformOrigin": "bottom right",
            "--rx-popup-offset": "8px",
            "--rx-popup-shift": "2px",
            "zIndex": "5",
        },
        {},
        {
            "display": "flex",
            "alignItems": "center",
            "height": "var(--select-item-height)",
            "paddingLeft": "var(--select-item-indicator-width)",
            "paddingRight": "var(--select-item-indicator-width)",
            "userSelect": "none",
            "fontSize": "var(--rx-select-label-font-size)",
            "lineHeight": "var(--rx-select-line-height)",
            "letterSpacing": "var(--rx-select-label-letter-spacing)",
            "color": "var(--gray-a10)",
            "cursor": "default",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "height": "var(--select-item-height)",
            "paddingLeft": "var(--select-item-indicator-width)",
            "paddingRight": "var(--select-item-indicator-width)",
            "userSelect": "none",
            "fontSize": "var(--rx-select-font-size)",
            "lineHeight": "var(--rx-select-line-height)",
            "letterSpacing": "var(--rx-select-letter-spacing)",
            "position": "relative",
            "boxSizing": "border-box",
            "outlineStyle": "none",
            "scrollMarginTop": "var(--select-content-padding)",
            "scrollMarginBottom": "var(--select-content-padding)",
            "borderRadius": "var(--rx-select-item-radius)",
            "cursor": {
                "default": "var(--cursor-menu-item)",
                "[aria-disabled='true']": "default",
            },
            "color": {
                "default": "inherit",
                ":focus": "var(--rx-select-highlight-color, inherit)",
                "[aria-disabled='true']": "var(--gray-a8)",
            },
            "backgroundColor": {":focus": "var(--rx-select-highlight)"},
            "--rx-select-check": {
                "default": "none",
                "[aria-selected='true']": "inline-flex",
            },
        },
        {
            "position": "absolute",
            "left": "0",
            "width": "var(--select-item-indicator-width)",
            "display": "var(--rx-select-check)",
            "alignItems": "center",
            "justifyContent": "center",
        },
        {
            "width": "var(--rx-select-check-size)",
            "height": "var(--rx-select-check-size)",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "height": "var(--select-item-height)",
            "paddingLeft": "var(--select-item-indicator-width)",
            "paddingRight": "var(--select-item-indicator-width)",
            "userSelect": "none",
            "fontSize": "var(--rx-select-font-size)",
            "lineHeight": "var(--rx-select-line-height)",
            "letterSpacing": "var(--rx-select-letter-spacing)",
            "position": "relative",
            "boxSizing": "border-box",
            "outlineStyle": "none",
            "scrollMarginTop": "var(--select-content-padding)",
            "scrollMarginBottom": "var(--select-content-padding)",
            "borderRadius": "var(--rx-select-item-radius)",
            "cursor": {
                "default": "var(--cursor-menu-item)",
                "[aria-disabled='true']": "default",
            },
            "color": {
                "default": "inherit",
                ":focus": "var(--rx-select-highlight-color, inherit)",
                "[aria-disabled='true']": "var(--gray-a8)",
            },
            "backgroundColor": {":focus": "var(--rx-select-highlight)"},
            "--rx-select-check": {
                "default": "none",
                "[aria-selected='true']": "inline-flex",
            },
        },
        {
            "position": "absolute",
            "left": "0",
            "width": "var(--select-item-indicator-width)",
            "display": "var(--rx-select-check)",
            "alignItems": "center",
            "justifyContent": "center",
        },
        {
            "width": "var(--rx-select-check-size)",
            "height": "var(--rx-select-check-size)",
        },
        {
            "height": "1px",
            "marginTop": "var(--space-2)",
            "marginBottom": "var(--space-2)",
            "marginLeft": "var(--select-item-indicator-width)",
            "marginRight": "var(--select-separator-margin-right)",
            "backgroundColor": "var(--gray-a6)",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "height": "var(--select-item-height)",
            "paddingLeft": "var(--select-item-indicator-width)",
            "paddingRight": "var(--select-item-indicator-width)",
            "userSelect": "none",
            "fontSize": "var(--rx-select-font-size)",
            "lineHeight": "var(--rx-select-line-height)",
            "letterSpacing": "var(--rx-select-letter-spacing)",
            "position": "relative",
            "boxSizing": "border-box",
            "outlineStyle": "none",
            "scrollMarginTop": "var(--select-content-padding)",
            "scrollMarginBottom": "var(--select-content-padding)",
            "borderRadius": "var(--rx-select-item-radius)",
            "cursor": {
                "default": "var(--cursor-menu-item)",
                "[aria-disabled='true']": "default",
            },
            "color": {
                "default": "inherit",
                ":focus": "var(--rx-select-highlight-color, inherit)",
                "[aria-disabled='true']": "var(--gray-a8)",
            },
            "backgroundColor": {":focus": "var(--rx-select-highlight)"},
            "--rx-select-check": {
                "default": "none",
                "[aria-selected='true']": "inline-flex",
            },
        },
        {
            "position": "absolute",
            "left": "0",
            "width": "var(--select-item-indicator-width)",
            "display": "var(--rx-select-check)",
            "alignItems": "center",
            "justifyContent": "center",
        },
        {
            "width": "var(--rx-select-check-size)",
            "height": "var(--rx-select-check-size)",
        },
        {
            "position": "absolute",
            "width": "1px",
            "height": "1px",
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
            "opacity": 0,
            "pointerEvents": "none",
        },
    ]


def test_select_of_a_list(
    ui_plugin: UIPlugin,
):
    """The select of a list of words has an option for each, in a group named by its label, and gives its trigger and its list what is theirs."""
    component = rx.ui.select(
        ["One", "Two"],
        label="Numbers",
        placeholder="Count",
        default_value="Two",
        variant="soft",
        radius="small",
        color_scheme="ruby",
        high_contrast=True,
        width="120px",
        id="count",
        name="count",
        position="item-aligned",
    )
    assert component.render() == {
        "name": '"span"',
        "props": [
            "className:sx_71b84cd269_c",
            '"data-rx-select":""',
            "onClick:selectClick",
            "onKeyDown:selectKeyDown",
            "onPointerMove:selectPointerMove",
        ],
        "children": [
            {
                "name": '"button"',
                "props": [
                    '"aria-autocomplete":"none"',
                    '"aria-controls":"rx-select-2"',
                    '"aria-expanded":"false"',
                    '"aria-haspopup":"listbox"',
                    'className:sx_476d055388_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_6d1e87c3d8',
                    '"data-state":"closed"',
                    'id:"count"',
                    'popovertarget:"rx-select-2"',
                    "ref:ref_count",
                    'role:"combobox"',
                    'type:"button"',
                ],
                "children": [
                    {
                        "name": '"span"',
                        "props": [
                            "className:sx_94480a599d_c",
                            '"data-placeholder":"Count"',
                            '"data-rx-select-shown":""',
                        ],
                        "children": [{"contents": '"Two"'}],
                    },
                    {
                        "name": '"svg"',
                        "props": [
                            '"aria-hidden":true',
                            "className:sx_3c2399b961_c",
                            'fill:"currentcolor"',
                            'height:"9"',
                            'viewBox:"0 0 9 9"',
                            'width:"9"',
                            'xmlns:"http://www.w3.org/2000/svg"',
                        ],
                        "children": [
                            {
                                "name": '"path"',
                                "props": [
                                    'd:"M0.135232 3.15803C0.324102 2.95657 0.640521 2.94637 0.841971 3.13523L4.5 6.56464L8.158 3.13523C8.3595 2.94637 8.6759 2.95657 8.8648 3.15803C9.0536 3.35949 9.0434 3.67591 8.842 3.86477L4.84197 7.6148C4.64964 7.7951 4.35036 7.7951 4.15803 7.6148L0.158031 3.86477C-0.0434285 3.67591 -0.0536285 3.35949 0.135232 3.15803Z"'
                                ],
                                "children": [],
                            }
                        ],
                    },
                ],
            },
            {
                "name": '"div"',
                "props": [
                    'className:sx_d08c2fb679_c + " " + reflexUIClasses_e201574881',
                    '"data-rx-popup":""',
                    'id:"rx-select-2"',
                    "onToggle:selectToggle",
                    'popover:"auto"',
                    'role:"listbox"',
                    "tabIndex:-1",
                ],
                "children": [
                    {
                        "name": '"div"',
                        "props": [
                            '"aria-labelledby":"rx-select-label-1"',
                            'role:"group"',
                        ],
                        "children": [
                            {
                                "name": '"div"',
                                "props": [
                                    "className:sx_4c825b9931_c",
                                    '"data-rx-select-label":""',
                                    'id:"rx-select-label-1"',
                                ],
                                "children": [{"contents": '"Numbers"'}],
                            },
                            {
                                "name": '"div"',
                                "props": [
                                    '"aria-selected":"false"',
                                    "className:sx_afbb711e7e_c",
                                    '"data-value":"One"',
                                    'role:"option"',
                                    "tabIndex:-1",
                                ],
                                "children": [
                                    {
                                        "name": '"span"',
                                        "props": ["className:sx_9209c0ff85_c"],
                                        "children": [
                                            {
                                                "name": '"svg"',
                                                "props": [
                                                    '"aria-hidden":true',
                                                    "className:sx_26fb6ce487_c",
                                                    'fill:"currentcolor"',
                                                    'height:"9"',
                                                    'viewBox:"0 0 9 9"',
                                                    'width:"9"',
                                                    'xmlns:"http://www.w3.org/2000/svg"',
                                                ],
                                                "children": [
                                                    {
                                                        "name": '"path"',
                                                        "props": [
                                                            'clipRule:"evenodd"',
                                                            'd:"M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z"',
                                                            'fillRule:"evenodd"',
                                                        ],
                                                        "children": [],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    {
                                        "name": '"span"',
                                        "props": ['"data-rx-select-text":""'],
                                        "children": [{"contents": '"One"'}],
                                    },
                                ],
                            },
                            {
                                "name": '"div"',
                                "props": [
                                    '"aria-selected":"true"',
                                    "className:sx_afbb711e7e_c",
                                    '"data-value":"Two"',
                                    'role:"option"',
                                    "tabIndex:-1",
                                ],
                                "children": [
                                    {
                                        "name": '"span"',
                                        "props": ["className:sx_9209c0ff85_c"],
                                        "children": [
                                            {
                                                "name": '"svg"',
                                                "props": [
                                                    '"aria-hidden":true',
                                                    "className:sx_26fb6ce487_c",
                                                    'fill:"currentcolor"',
                                                    'height:"9"',
                                                    'viewBox:"0 0 9 9"',
                                                    'width:"9"',
                                                    'xmlns:"http://www.w3.org/2000/svg"',
                                                ],
                                                "children": [
                                                    {
                                                        "name": '"path"',
                                                        "props": [
                                                            'clipRule:"evenodd"',
                                                            'd:"M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z"',
                                                            'fillRule:"evenodd"',
                                                        ],
                                                        "children": [],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    {
                                        "name": '"span"',
                                        "props": ['"data-rx-select-text":""'],
                                        "children": [{"contents": '"Two"'}],
                                    },
                                ],
                            },
                        ],
                    }
                ],
            },
            {
                "name": '"input"',
                "props": [
                    '"aria-hidden":true',
                    "className:sx_b72d7382fd_c",
                    '"data-rx-select-value":""',
                    'defaultValue:"Two"',
                    'name:"count"',
                    "onFocus:selectFocus",
                    "ref:((holder) => syncSelect(holder, null, null))",
                    "tabIndex:-1",
                ],
                "children": [],
            },
        ],
    }


def test_select_default_styles(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The styles of a select that is given no props, whose first option is in no group."""
    component = rx.ui.select.root(
        rx.ui.select.trigger(), rx.ui.select.content(rx.ui.select.item("A", value="a"))
    )
    assert declared_styles(component) == [
        {"display": "contents"},
        {
            "appearance": "none",
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
                "default": "var(--color-surface)",
                ":disabled": "var(--gray-a2)",
            },
            "backgroundImage": "none",
            "textTransform": "inherit",
            "textIndent": "initial",
            "wordSpacing": "inherit",
            "cursor": {
                "default": "var(--cursor-button)",
                ":disabled": "var(--cursor-disabled)",
            },
            "WebkitTapHighlightColor": "transparent",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "flexShrink": 0,
            "userSelect": "none",
            "verticalAlign": "top",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "outlineStyle": {"default": "none", ":focus-visible": "solid"},
            "outlineWidth": {"default": "medium", ":focus-visible": "2px"},
            "outlineColor": {
                "default": "currentcolor",
                ":focus-visible": "var(--focus-8)",
            },
            "outlineOffset": {"default": "0", ":focus-visible": "-1px"},
            "--rx-select-icon-color": {":disabled": "var(--gray-a9)"},
            "--select-trigger-height": "var(--space-6)",
            "gap": "calc(var(--space-1) * 1.5)",
            "fontSize": "var(--font-size-2)",
            "lineHeight": "var(--line-height-2)",
            "letterSpacing": "var(--letter-spacing-2)",
            "borderRadius": "max(var(--radius-2), var(--radius-full))",
            "boxSizing": "border-box",
            "height": "var(--select-trigger-height)",
            "--rx-select-shown-color": {"[data-placeholder]": "var(--gray-a10)"},
            "color": {"default": "var(--gray-12)", ":disabled": "var(--gray-a11)"},
            "boxShadow": {
                "default": "inset 0 0 0 1px var(--gray-a7)",
                "@media (hover: hover)": {
                    ":hover:not(:disabled)": "inset 0 0 0 1px var(--gray-a8)"
                },
                ":is([data-state='open'], :has(+ :popover-open)):not(:disabled)": "inset 0 0 0 1px var(--gray-a8)",
                ":disabled": "inset 0 0 0 1px var(--gray-a6)",
            },
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "textOverflow": "ellipsis",
            "whiteSpace": "nowrap",
            "color": "var(--rx-select-shown-color, inherit)",
            "opacity": "var(--rx-select-shown-opacity, 1)",
        },
        {
            "flexShrink": 0,
            "color": "var(--rx-select-icon-color, inherit)",
            "opacity": 0.9,
        },
        {
            "position": "fixed",
            "top": "auto",
            "right": "auto",
            "bottom": "auto",
            "left": "auto",
            "marginTop": "var(--rx-popup-offset, 4px)",
            "marginRight": "0",
            "marginBottom": "var(--rx-popup-offset, 4px)",
            "marginLeft": "var(--rx-popup-shift, 0px)",
            "padding": "var(--select-content-padding)",
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
            "maxWidth": "calc(100vw - 10px * 2)",
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
            "color": "var(--gray-12)",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "backgroundColor": "var(--color-panel-solid)",
            "boxShadow": "var(--shadow-5)",
            "minWidth": "anchor-size(width)",
            "outlineStyle": "none",
            "overflowY": "auto",
            "scrollbarWidth": "thin",
            "scrollbarColor": "var(--gray-a8) transparent",
            "--select-content-padding": "var(--space-2)",
            "--select-item-height": "var(--space-6)",
            "--select-item-indicator-width": "var(--space-5)",
            "--select-separator-margin-right": "var(--space-3)",
            "borderTopLeftRadius": "var(--radius-4)",
            "borderTopRightRadius": "var(--radius-4)",
            "borderBottomRightRadius": "var(--radius-4)",
            "borderBottomLeftRadius": "var(--radius-4)",
            "--rx-select-font-size": "var(--font-size-2)",
            "--rx-select-line-height": "var(--line-height-2)",
            "--rx-select-letter-spacing": "var(--letter-spacing-2)",
            "--rx-select-label-font-size": "var(--font-size-2)",
            "--rx-select-label-letter-spacing": "var(--letter-spacing-2)",
            "--rx-select-item-radius": "var(--radius-2)",
            "--rx-select-check-size": "calc(10px * var(--scaling))",
            "--rx-select-highlight": "var(--accent-9)",
            "--rx-select-highlight-color": "var(--accent-contrast)",
            "positionArea": "bottom span-right",
            "maxHeight": "calc(100% - var(--rx-popup-offset, 4px) - 10px)",
            "--rx-popup-from": "translateY(-4px) scale(0.97)",
            "transformOrigin": "top left",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "height": "var(--select-item-height)",
            "paddingLeft": "var(--select-item-indicator-width)",
            "paddingRight": "var(--select-item-indicator-width)",
            "userSelect": "none",
            "fontSize": "var(--rx-select-font-size)",
            "lineHeight": "var(--rx-select-line-height)",
            "letterSpacing": "var(--rx-select-letter-spacing)",
            "position": "relative",
            "boxSizing": "border-box",
            "outlineStyle": "none",
            "scrollMarginTop": "var(--select-content-padding)",
            "scrollMarginBottom": "var(--select-content-padding)",
            "borderRadius": "var(--rx-select-item-radius)",
            "cursor": {
                "default": "var(--cursor-menu-item)",
                "[aria-disabled='true']": "default",
            },
            "color": {
                "default": "inherit",
                ":focus": "var(--rx-select-highlight-color, inherit)",
                "[aria-disabled='true']": "var(--gray-a8)",
            },
            "backgroundColor": {":focus": "var(--rx-select-highlight)"},
            "--rx-select-check": {
                "default": "none",
                "[aria-selected='true']": "inline-flex",
            },
        },
        {
            "position": "absolute",
            "left": "0",
            "width": "var(--select-item-indicator-width)",
            "display": "var(--rx-select-check)",
            "alignItems": "center",
            "justifyContent": "center",
        },
        {
            "width": "var(--rx-select-check-size)",
            "height": "var(--rx-select-check-size)",
        },
        {
            "position": "absolute",
            "width": "1px",
            "height": "1px",
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
            "opacity": 0,
            "pointerEvents": "none",
        },
    ]


def test_select_ghost_styles(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The ghost trigger, and a list beside its trigger and centered on it."""
    component = rx.ui.select.root(
        rx.ui.select.trigger(variant="ghost"),
        rx.ui.select.content(side="left", align="center"),
        size="1",
    )
    assert declared_styles(component) == [
        {"display": "contents"},
        {
            "appearance": "none",
            "marginTop": "calc(0px - var(--select-trigger-ghost-padding-y))",
            "marginRight": "calc(0px - var(--select-trigger-ghost-padding-x))",
            "marginBottom": "calc(0px - var(--select-trigger-ghost-padding-y))",
            "marginLeft": "calc(0px - var(--select-trigger-ghost-padding-x))",
            "paddingTop": "var(--select-trigger-ghost-padding-y)",
            "paddingRight": "var(--select-trigger-ghost-padding-x)",
            "paddingBottom": "var(--select-trigger-ghost-padding-y)",
            "paddingLeft": "var(--select-trigger-ghost-padding-x)",
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
                "@media (hover: hover)": {":hover:not(:disabled)": "var(--accent-a3)"},
                ":is([data-state='open'], :has(+ :popover-open)):not(:disabled)": "var(--accent-a3)",
                ":disabled": "transparent",
            },
            "backgroundImage": "none",
            "textTransform": "inherit",
            "textIndent": "initial",
            "wordSpacing": "inherit",
            "cursor": {
                "default": "var(--cursor-button)",
                ":disabled": "var(--cursor-disabled)",
            },
            "WebkitTapHighlightColor": "transparent",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "flexShrink": 0,
            "userSelect": "none",
            "verticalAlign": "top",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "outlineStyle": {"default": "none", ":focus-visible": "solid"},
            "outlineWidth": {"default": "medium", ":focus-visible": "2px"},
            "outlineColor": {
                "default": "currentcolor",
                ":focus-visible": "var(--focus-8)",
            },
            "outlineOffset": {"default": "0", ":focus-visible": "-1px"},
            "--rx-select-icon-color": {":disabled": "var(--gray-a9)"},
            "--select-trigger-height": "var(--space-5)",
            "rowGap": "var(--space-1)",
            "columnGap": "var(--space-1)",
            "fontSize": "var(--font-size-1)",
            "lineHeight": "var(--line-height-1)",
            "letterSpacing": "var(--letter-spacing-1)",
            "borderRadius": "max(var(--radius-1), var(--radius-full))",
            "--rx-select-shown-color": {"[data-placeholder]": "var(--accent-12)"},
            "--rx-select-shown-opacity": {"[data-placeholder]": 0.6},
            "boxSizing": "content-box",
            "height": "fit-content",
            "color": {"default": "var(--accent-12)", ":disabled": "var(--gray-a11)"},
            "--select-trigger-ghost-padding-x": "var(--space-2)",
            "--select-trigger-ghost-padding-y": "var(--space-1)",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "textOverflow": "ellipsis",
            "whiteSpace": "nowrap",
            "color": "var(--rx-select-shown-color, inherit)",
            "opacity": "var(--rx-select-shown-opacity, 1)",
        },
        {"flexShrink": 0, "color": "var(--rx-select-icon-color, inherit)"},
        {
            "position": "fixed",
            "top": "auto",
            "right": "auto",
            "bottom": "auto",
            "left": "auto",
            "marginTop": "0",
            "marginRight": "var(--rx-popup-offset, 4px)",
            "marginBottom": "0",
            "marginLeft": "var(--rx-popup-offset, 4px)",
            "padding": "var(--select-content-padding)",
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
            "maxWidth": "calc(100% - var(--rx-popup-offset, 4px) - 10px)",
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
            "color": "var(--gray-12)",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "backgroundColor": "var(--color-panel-solid)",
            "boxShadow": "var(--shadow-5)",
            "minWidth": "anchor-size(width)",
            "outlineStyle": "none",
            "overflowY": "auto",
            "scrollbarWidth": "thin",
            "scrollbarColor": "var(--gray-a8) transparent",
            "--select-content-padding": "var(--space-1)",
            "--select-item-height": "var(--space-5)",
            "--select-item-indicator-width": "calc(var(--space-5) / 1.2)",
            "--select-separator-margin-right": "var(--space-2)",
            "borderTopLeftRadius": "var(--radius-3)",
            "borderTopRightRadius": "var(--radius-3)",
            "borderBottomRightRadius": "var(--radius-3)",
            "borderBottomLeftRadius": "var(--radius-3)",
            "--rx-select-font-size": "var(--font-size-1)",
            "--rx-select-line-height": "var(--line-height-1)",
            "--rx-select-letter-spacing": "var(--letter-spacing-1)",
            "--rx-select-label-font-size": "var(--font-size-1)",
            "--rx-select-label-letter-spacing": "var(--letter-spacing-1)",
            "--rx-select-item-radius": "var(--radius-1)",
            "--rx-select-check-size": "calc(8px * var(--scaling))",
            "--rx-select-highlight": "var(--accent-9)",
            "--rx-select-highlight-color": "var(--accent-contrast)",
            "positionArea": "left span-all",
            "--rx-popup-from": "translateX(4px) scale(0.97)",
            "transformOrigin": "right center",
            "alignSelf": "anchor-center",
        },
        {
            "position": "absolute",
            "width": "1px",
            "height": "1px",
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
            "opacity": 0,
            "pointerEvents": "none",
        },
    ]


def test_select_unknown_variant(ui_plugin: UIPlugin):
    """A variant a trigger does not have is an error that lists the ones it has."""
    with pytest.raises(StyleError) as error:
        rx.ui.select.trigger(variant="solid")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == 'rx.ui.select_trigger: unknown variant "solid". The values are "classic", "surface", "soft", "ghost".'
    )


def test_select_unknown_side(ui_plugin: UIPlugin):
    """A side a list cannot be on is an error that lists the sides."""
    with pytest.raises(StyleError) as error:
        rx.ui.select.content(side="above")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == 'rx.ui.select_content: unknown side "above". The values are "top", "right", "bottom", "left".'
    )


def test_select_of_a_list_unknown_variant(ui_plugin: UIPlugin):
    """The select of a list of words fails as its trigger does."""
    with pytest.raises(StyleError) as error:
        rx.ui.select(["a"], variant="outline")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == 'rx.ui.select_trigger: unknown variant "outline". The values are "classic", "surface", "soft", "ghost".'
    )


STATE = (
    "reflex___state____state__tests___units___reflex_components_ui"
    "___components___test_select____select_state"
)
HANDLER = (
    "reflex___state____state.tests___units___reflex_components_ui"
    "___components___test_select____select_state"
)


def _event(handler: str, argument: str) -> str:
    """Write the function an event handler with one argument renders as.

    Args:
        handler: The name of the handler.
        argument: The name of its argument.

    Returns:
        The function.
    """
    return (
        f'((_ev_0) => (addEvents([(ReflexEvent("{HANDLER}.{handler}", '
        f'({{ ["{argument}"] : _ev_0 }}), ({{  }})))], [_ev_0], ({{  }}))))'
    )


def test_select_bound_to_state(ui_plugin: UIPlugin):
    """A select bound to state hands its value and whether it is open to its script, and its events to the input and the popover."""
    select = rx.ui.select.root(
        rx.ui.select.trigger(placeholder="Pick"),
        rx.ui.select.content(
            rx.ui.select.item("Apple", value="apple"),
            rx.ui.select.item("Pear", value="pear"),
            side_offset=SelectState.offset,
            on_close_auto_focus=SelectState.closed,
            on_escape_key_down=SelectState.closed,
            on_pointer_down_outside=SelectState.closed,
        ),
        value=SelectState.fruit,
        open=SelectState.is_open,
        on_change=SelectState.set_fruit,
        on_open_change=SelectState.set_is_open,
    )
    fruit = f"{STATE}.fruit_rx_state_"
    closed = (
        f'((...args) => (addEvents([(ReflexEvent("{HANDLER}.closed", ({{  }}), '
        "({  })))], args, ({  }))))"
    )
    trigger, content, holder = select.children
    assert select.render()["props"] == [
        "className:sx_71b84cd269_c",
        '"data-rx-select":""',
        (
            f'onChange:((_e) => (addEvents([(ReflexEvent("{HANDLER}.set_fruit", '
            '({ ["fruit"] : _e?.["target"]?.["value"] }), ({  })))], [_e], ({  }))))'
        ),
        "onClick:selectClick",
        "onKeyDown:selectKeyDown",
        "onPointerMove:selectPointerMove",
    ]
    assert trigger.render()["props"] == [
        '"aria-autocomplete":"none"',
        '"aria-controls":"rx-select-1"',
        '"aria-expanded":"false"',
        '"aria-haspopup":"listbox"',
        "className:sx_872142009a_c",
        f'"data-placeholder":({fruit} ? undefined : "")',
        '"data-state":"closed"',
        'popovertarget:"rx-select-1"',
        'role:"combobox"',
        'type:"button"',
    ]
    assert trigger.children[0].render() == {
        "name": '"span"',
        "props": [
            "className:sx_94480a599d_c",
            '"data-placeholder":"Pick"',
            '"data-rx-select-shown":""',
        ],
        "children": [
            {
                "contents": (
                    '(({ ["apple"] : "Apple", ["pear"] : "Pear" })'
                    f'[{fruit}] ?? "Pick")'
                )
            }
        ],
    }
    assert content.render()["props"] == [
        "className:sx_bb2bcf4a84_c",
        '"data-rx-popup":""',
        'id:"rx-select-1"',
        (
            "onToggle:((event) => selectToggle(event, ({ "
            f"open: {_event('set_is_open', 'is_open')}, "
            f"close: {closed}, escape: {closed}, outside: {closed} }})))"
        ),
        'popover:"auto"',
        'role:"listbox"',
        (f'style:({{ "--v0": ((({STATE}.offset_rx_state_) + "px")) ?? "initial" }})'),
        "tabIndex:-1",
    ]
    assert str(content._element_styles().style.style["--rx-popup-offset"]) == (  # pyright: ignore[reportAttributeAccessIssue]
        f'(({STATE}.offset_rx_state_) + "px")'
    )
    assert [item.render()["props"] for item in content.children] == [
        [
            f'"aria-selected":(({fruit} === "{value}") ? "true" : "false")',
            "className:sx_afbb711e7e_c",
            f'"data-value":"{value}"',
            'role:"option"',
            "tabIndex:-1",
        ]
        for value in ("apple", "pear")
    ]
    assert holder.render()["props"] == [
        '"aria-hidden":true',
        "className:sx_b72d7382fd_c",
        '"data-rx-select-value":""',
        f"defaultValue:{fruit}",
        "onFocus:selectFocus",
        (f"ref:((holder) => syncSelect(holder, {fruit}, {STATE}.is_open_rx_state_))"),
        "tabIndex:-1",
    ]


def test_select_of_a_list_in_state(ui_plugin: UIPlugin):
    """Options a foreach renders show their values, so the trigger shows the value of the select."""
    select = rx.ui.select(SelectState.fruits, value=SelectState.fruit)
    trigger, content, _ = select.children
    assert trigger.children[0].render()["children"] == [
        {"contents": f'({STATE}.fruit_rx_state_ || "")'}
    ]
    (group,) = content.children
    (options,) = group.children
    item = options.children[0]
    assert item.render()["props"] == [
        (
            f'"aria-selected":(({STATE}.fruit_rx_state_ === item_rx_state_) '
            '? "true" : "false")'
        ),
        "className:sx_afbb711e7e_c",
        '"data-value":item_rx_state_',
        "key:index_d6d6157c99650830f12a866606ea87b7",
        'role:"option"',
        "tabIndex:-1",
    ]


def test_select_shows_what_it_knows(ui_plugin: UIPlugin):
    """The trigger shows the placeholder for a value no option has, for options that hold more than text, and what it is given in place of either."""
    item, trigger, content = (
        rx.ui.select.item,
        rx.ui.select.trigger,
        rx.ui.select.content,
    )

    def shown(*options: Any, trigger_children: tuple[Any, ...] = (), **props: Any):
        root = rx.ui.select.root(
            trigger(*trigger_children, placeholder="Pick"), content(*options), **props
        )
        rendered = root.children[0].children[0].render()
        return rendered["props"], rendered["children"]

    mark = [
        "className:sx_94480a599d_c",
        '"data-placeholder":"Pick"',
        '"data-rx-select-shown":""',
    ]
    assert shown(item("A", value="a")) == (mark, [{"contents": '"Pick"'}])
    assert shown(item("A", value="a"), default_value="b") == (
        mark,
        [{"contents": '"Pick"'}],
    )
    assert shown(item(rx.el.b("A"), value="a"), default_value="a") == (
        mark,
        [{"contents": '"Pick"'}],
    )
    assert shown(item(rx.el.b("A"), value="a"), value=SelectState.fruit) == (
        mark,
        [{"contents": '"Pick"'}],
    )
    assert shown(
        item("A", value="a"), trigger_children=("Custom",), default_value="a"
    ) == (["className:sx_94480a599d_c"], [{"contents": '"Custom"'}])


def test_select_script(ui_plugin: UIPlugin):
    """The script of a select is imported by the parts that call it."""
    select = rx.ui.select(["a"])
    assert select._get_all_imports()["$/reflex-ui/behaviors/listbox.js"] == [
        ImportVar(tag="selectKeyDown"),
        ImportVar(tag="selectClick"),
        ImportVar(tag="selectPointerMove"),
        ImportVar(tag="selectToggle"),
        ImportVar(tag="syncSelect"),
        ImportVar(tag="selectFocus"),
    ]
