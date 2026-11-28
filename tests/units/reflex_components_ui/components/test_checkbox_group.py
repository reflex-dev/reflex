"""Tests for reflex_components_ui.components.checkbox_group."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


class CheckboxGroupState(rx.State):
    """What a checkbox group is bound to."""

    picked: list[str] = ["a"]

    @rx.event
    def pick(self, picked: list[str]):
        """Follow the group.

        Args:
            picked: The values of the checked items.
        """
        self.picked = picked


def test_checkbox_group(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The items of a group are native checkboxes with its name, its look and its state; one with children is in a label."""
    component = rx.ui.checkbox_group.root(
        rx.ui.checkbox_group.item("One", value="1", id="one", margin="1px"),
        rx.ui.checkbox_group.item(value="2", disabled=True),
        rx.el.div(rx.ui.checkbox_group.item(value="3")),
        default_value=["2", "3"],
        name="pick",
        size="3",
        variant="soft",
        high_contrast=True,
        color_scheme="ruby",
        id="group",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            'className:sx_a088d40a93_c + " " + reflexUIClasses_e201574881',
            'id:"group"',
            "ref:ref_group",
            'role:"group"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_ab61f35f5f_c"],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_0710e9ad14_c",
                            'id:"one"',
                            'name:"pick"',
                            "ref:ref_one",
                            'type:"checkbox"',
                            'value:"1"',
                        ],
                        "children": [],
                    },
                    {
                        "name": '"span"',
                        "props": ["className:sx_1107ef58c5_c"],
                        "children": [{"contents": '"One"'}],
                    },
                ],
            },
            {
                "name": '"input"',
                "props": [
                    "className:sx_0710e9ad14_c",
                    "defaultChecked:true",
                    "disabled:true",
                    'name:"pick"',
                    'type:"checkbox"',
                    'value:"2"',
                ],
                "children": [],
            },
            {
                "name": '"div"',
                "props": [],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_0710e9ad14_c",
                            "defaultChecked:true",
                            'name:"pick"',
                            'type:"checkbox"',
                            'value:"3"',
                        ],
                        "children": [],
                    }
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexDirection": "column",
            "rowGap": "var(--space-1)",
            "columnGap": "var(--space-1)",
        },
        {
            "marginTop": "1px",
            "marginRight": "1px",
            "marginBottom": "1px",
            "marginLeft": "1px",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--font-size-3)",
            "--line-height": "var(--line-height-3)",
            "--letter-spacing": "var(--letter-spacing-3)",
            "WebkitTapHighlightColor": {"@media (pointer: coarse)": "transparent"},
            "outlineWidth": {"@media (pointer: coarse)": {":active": "0.75em"}},
            "outlineStyle": {"@media (pointer: coarse)": {":active": "solid"}},
            "outlineColor": {"@media (pointer: coarse)": {":active": "var(--gray-a4)"}},
            "outlineOffset": {"@media (pointer: coarse)": {":active": "-0.6em"}},
        },
        {
            "appearance": "none",
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
                "::before": {
                    "default": "var(--accent-a5)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": {
                    "default": "var(--accent-12)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": "inherit",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textIndent": "initial",
            "outlineStyle": {
                "default": "none",
                "::before": {":focus-visible": "solid"},
            },
            "outlineWidth": {
                "default": "medium",
                "::before": {":focus-visible": "2px"},
            },
            "outlineColor": {
                "default": "currentcolor",
                "::before": {":focus-visible": "var(--focus-8)"},
            },
            "outlineOffset": {"default": "0", "::before": {":focus-visible": "2px"}},
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "relative", "::after": "absolute"},
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": {
                "default": "var(--cursor-checkbox)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--checkbox-size))",
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "content": {
                "::before": "''",
                "::after": {":is(:checked, :indeterminate)": "''"},
            },
            "width": {
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "borderRadius": {"::before": "var(--checkbox-border-radius)"},
            "transform": {"::after": "translate(-50%, -50%)"},
            "top": {"::after": "50%"},
            "left": {"::after": "50%"},
            "pointerEvents": {"::after": "none"},
            "maskImage": {
                "::after": {
                    "default": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z'/%3E%3C/svg%3E\")",
                    ":indeterminate": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 4.91421 0.75 4.5Z'/%3E%3C/svg%3E\")",
                }
            },
            "maskSize": {"::after": "100% 100%"},
            "maskRepeat": {"::after": "no-repeat"},
            "--checkbox-size": "calc(var(--space-4) * 1.25)",
            "--checkbox-indicator-size": "calc(12px * var(--scaling))",
            "--checkbox-border-radius": "calc(var(--radius-1) * 1.25)",
        },
        {"minWidth": 0},
        {
            "appearance": "none",
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
                "::before": {
                    "default": "var(--accent-a5)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": {
                    "default": "var(--accent-12)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": "inherit",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textIndent": "initial",
            "outlineStyle": {
                "default": "none",
                "::before": {":focus-visible": "solid"},
            },
            "outlineWidth": {
                "default": "medium",
                "::before": {":focus-visible": "2px"},
            },
            "outlineColor": {
                "default": "currentcolor",
                "::before": {":focus-visible": "var(--focus-8)"},
            },
            "outlineOffset": {"default": "0", "::before": {":focus-visible": "2px"}},
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "relative", "::after": "absolute"},
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": {
                "default": "var(--cursor-checkbox)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--checkbox-size))",
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "content": {
                "::before": "''",
                "::after": {":is(:checked, :indeterminate)": "''"},
            },
            "width": {
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "borderRadius": {"::before": "var(--checkbox-border-radius)"},
            "transform": {"::after": "translate(-50%, -50%)"},
            "top": {"::after": "50%"},
            "left": {"::after": "50%"},
            "pointerEvents": {"::after": "none"},
            "maskImage": {
                "::after": {
                    "default": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z'/%3E%3C/svg%3E\")",
                    ":indeterminate": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 4.91421 0.75 4.5Z'/%3E%3C/svg%3E\")",
                }
            },
            "maskSize": {"::after": "100% 100%"},
            "maskRepeat": {"::after": "no-repeat"},
            "--checkbox-size": "calc(var(--space-4) * 1.25)",
            "--checkbox-indicator-size": "calc(12px * var(--scaling))",
            "--checkbox-border-radius": "calc(var(--radius-1) * 1.25)",
        },
        {
            "appearance": "none",
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
                "::before": {
                    "default": "var(--accent-a5)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": {
                    "default": "var(--accent-12)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": "inherit",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textIndent": "initial",
            "outlineStyle": {
                "default": "none",
                "::before": {":focus-visible": "solid"},
            },
            "outlineWidth": {
                "default": "medium",
                "::before": {":focus-visible": "2px"},
            },
            "outlineColor": {
                "default": "currentcolor",
                "::before": {":focus-visible": "var(--focus-8)"},
            },
            "outlineOffset": {"default": "0", "::before": {":focus-visible": "2px"}},
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "relative", "::after": "absolute"},
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": {
                "default": "var(--cursor-checkbox)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--checkbox-size))",
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "content": {
                "::before": "''",
                "::after": {":is(:checked, :indeterminate)": "''"},
            },
            "width": {
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "borderRadius": {"::before": "var(--checkbox-border-radius)"},
            "transform": {"::after": "translate(-50%, -50%)"},
            "top": {"::after": "50%"},
            "left": {"::after": "50%"},
            "pointerEvents": {"::after": "none"},
            "maskImage": {
                "::after": {
                    "default": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z'/%3E%3C/svg%3E\")",
                    ":indeterminate": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 4.91421 0.75 4.5Z'/%3E%3C/svg%3E\")",
                }
            },
            "maskSize": {"::after": "100% 100%"},
            "maskRepeat": {"::after": "no-repeat"},
            "--checkbox-size": "calc(var(--space-4) * 1.25)",
            "--checkbox-indicator-size": "calc(12px * var(--scaling))",
            "--checkbox-border-radius": "calc(var(--radius-1) * 1.25)",
        },
    ]


def test_checkbox_group_bound_to_state(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A bound group checks the items among its values, and a change hands over the values of the checked ones."""
    component = rx.ui.checkbox_group.root(
        rx.ui.checkbox_group.item(value="a"),
        rx.ui.checkbox_group.item("B", value="b"),
        value=CheckboxGroupState.picked,
        on_value_change=CheckboxGroupState.pick,
        name="pick",
        required=True,
        disabled=False,
        orientation="horizontal",
        loop=True,
        dir="rtl",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_a088d40a93_c",
            'dir:"rtl"',
            'onChange:((_e) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_checkbox_group____checkbox_group_state.pick", ({ ["picked"] : Array.from(_e.currentTarget.querySelectorAll("input[type=checkbox]:checked")).filter((input) => input.name === _e.target.name).map((input) => input.value) }), ({  })))], [_e], ({  }))))',
            'role:"group"',
        ],
        "children": [
            {
                "name": '"input"',
                "props": [
                    'checked:(reflex___state____state__tests___units___reflex_components_ui___components___test_checkbox_group____checkbox_group_state.picked_rx_state_.includes("a"))',
                    "className:sx_eda6ae65a6_c",
                    "disabled:false",
                    'name:"pick"',
                    "readOnly:true",
                    "required:true",
                    'type:"checkbox"',
                    'value:"a"',
                ],
                "children": [],
            },
            {
                "name": '"label"',
                "props": ["className:sx_d1083f6dbf_c"],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            'checked:(reflex___state____state__tests___units___reflex_components_ui___components___test_checkbox_group____checkbox_group_state.picked_rx_state_.includes("b"))',
                            "className:sx_eda6ae65a6_c",
                            "disabled:false",
                            'name:"pick"',
                            "readOnly:true",
                            "required:true",
                            'type:"checkbox"',
                            'value:"b"',
                        ],
                        "children": [],
                    },
                    {
                        "name": '"span"',
                        "props": ["className:sx_1107ef58c5_c"],
                        "children": [{"contents": '"B"'}],
                    },
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexDirection": "column",
            "rowGap": "var(--space-1)",
            "columnGap": "var(--space-1)",
        },
        {
            "appearance": "none",
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
                "::before": {
                    "default": "var(--color-surface)",
                    ":is(:checked, :indeterminate):not(:disabled)": "var(--accent-indicator)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": {
                    "default": "var(--accent-contrast)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": "inherit",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textIndent": "initial",
            "outlineStyle": {
                "default": "none",
                "::before": {":focus-visible": "solid"},
            },
            "outlineWidth": {
                "default": "medium",
                "::before": {":focus-visible": "2px"},
            },
            "outlineColor": {
                "default": "currentcolor",
                "::before": {":focus-visible": "var(--focus-8)"},
            },
            "outlineOffset": {"default": "0", "::before": {":focus-visible": "2px"}},
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "relative", "::after": "absolute"},
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": {
                "default": "var(--cursor-checkbox)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--checkbox-size))",
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "content": {
                "::before": "''",
                "::after": {":is(:checked, :indeterminate)": "''"},
            },
            "width": {
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "borderRadius": {"::before": "var(--checkbox-border-radius)"},
            "transform": {"::after": "translate(-50%, -50%)"},
            "top": {"::after": "50%"},
            "left": {"::after": "50%"},
            "pointerEvents": {"::after": "none"},
            "maskImage": {
                "::after": {
                    "default": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z'/%3E%3C/svg%3E\")",
                    ":indeterminate": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 4.91421 0.75 4.5Z'/%3E%3C/svg%3E\")",
                }
            },
            "maskSize": {"::after": "100% 100%"},
            "maskRepeat": {"::after": "no-repeat"},
            "--checkbox-size": "var(--space-4)",
            "--checkbox-indicator-size": "calc(10px * var(--scaling))",
            "--checkbox-border-radius": "var(--radius-1)",
            "boxShadow": {
                "::before": {
                    "default": "inset 0 0 0 1px var(--gray-a7)",
                    ":is(:checked, :indeterminate):not(:disabled)": "none",
                    ":disabled": "inset 0 0 0 1px var(--gray-a6)",
                }
            },
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--font-size-2)",
            "--line-height": "var(--line-height-2)",
            "--letter-spacing": "var(--letter-spacing-2)",
            "WebkitTapHighlightColor": {"@media (pointer: coarse)": "transparent"},
            "outlineWidth": {"@media (pointer: coarse)": {":active": "0.75em"}},
            "outlineStyle": {"@media (pointer: coarse)": {":active": "solid"}},
            "outlineColor": {"@media (pointer: coarse)": {":active": "var(--gray-a4)"}},
            "outlineOffset": {"@media (pointer: coarse)": {":active": "-0.6em"}},
        },
        {
            "appearance": "none",
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
                "::before": {
                    "default": "var(--color-surface)",
                    ":is(:checked, :indeterminate):not(:disabled)": "var(--accent-indicator)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": {
                    "default": "var(--accent-contrast)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": "inherit",
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textIndent": "initial",
            "outlineStyle": {
                "default": "none",
                "::before": {":focus-visible": "solid"},
            },
            "outlineWidth": {
                "default": "medium",
                "::before": {":focus-visible": "2px"},
            },
            "outlineColor": {
                "default": "currentcolor",
                "::before": {":focus-visible": "var(--focus-8)"},
            },
            "outlineOffset": {"default": "0", "::before": {":focus-visible": "2px"}},
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "relative", "::after": "absolute"},
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": {
                "default": "var(--cursor-checkbox)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--checkbox-size))",
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "content": {
                "::before": "''",
                "::after": {":is(:checked, :indeterminate)": "''"},
            },
            "width": {
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "borderRadius": {"::before": "var(--checkbox-border-radius)"},
            "transform": {"::after": "translate(-50%, -50%)"},
            "top": {"::after": "50%"},
            "left": {"::after": "50%"},
            "pointerEvents": {"::after": "none"},
            "maskImage": {
                "::after": {
                    "default": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z'/%3E%3C/svg%3E\")",
                    ":indeterminate": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 4.91421 0.75 4.5Z'/%3E%3C/svg%3E\")",
                }
            },
            "maskSize": {"::after": "100% 100%"},
            "maskRepeat": {"::after": "no-repeat"},
            "--checkbox-size": "var(--space-4)",
            "--checkbox-indicator-size": "calc(10px * var(--scaling))",
            "--checkbox-border-radius": "var(--radius-1)",
            "boxShadow": {
                "::before": {
                    "default": "inset 0 0 0 1px var(--gray-a7)",
                    ":is(:checked, :indeterminate):not(:disabled)": "none",
                    ":disabled": "inset 0 0 0 1px var(--gray-a6)",
                }
            },
        },
        {"minWidth": 0},
    ]


def test_checkbox_group_unknown_variant(ui_plugin: UIPlugin):
    """A variant a group does not have is an error that lists the ones it has."""
    with pytest.raises(TypeError) as error:
        rx.ui.checkbox_group.root(variant="solid")
    assert (
        str(error.value)
        == "Invalid var passed for prop CheckboxGroupRoot.variant, expected type typing.Literal['classic', 'surface', 'soft'], got value 'solid' of type <class 'str'>."
    )
