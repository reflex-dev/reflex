"""Tests for reflex_components_ui.components.checkbox_cards."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


class CardsState(rx.State):
    """What a group of cards is bound to."""

    picked: list[str] = ["a"]

    @rx.event
    def pick(self, picked: list[str]):
        """Follow the group.

        Args:
            picked: What is checked.
        """
        self.picked = picked


def test_checkbox_cards(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A card is a label around a native input, which the group gives its name, its look and its state."""
    component = rx.ui.checkbox_cards.root(
        rx.ui.checkbox_cards.item("One", value="1", id="one", margin="1px"),
        rx.ui.checkbox_cards.item("Two", value="2", disabled=True),
        default_value=["1"],
        name="pick",
        id="group",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_076463c881_c",
            'id:"group"',
            "ref:ref_group",
            'role:"group"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_26403764ed_c", '"data-rx-cards-item":""'],
                "children": [
                    {"contents": '"One"'},
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_e9aee32af5_c",
                            "defaultChecked:true",
                            'id:"one"',
                            'name:"pick"',
                            "ref:ref_one",
                            'type:"checkbox"',
                            'value:"1"',
                        ],
                        "children": [],
                    },
                ],
            },
            {
                "name": '"label"',
                "props": ["className:sx_12056722ee_c", '"data-rx-cards-item":""'],
                "children": [
                    {"contents": '"Two"'},
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_e9aee32af5_c",
                            "disabled:true",
                            'name:"pick"',
                            'type:"checkbox"',
                            'value:"2"',
                        ],
                        "children": [],
                    },
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "grid",
            "alignItems": "stretch",
            "justifyContent": "flex-start",
            "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))",
            "gridTemplateRows": "none",
            "rowGap": "var(--space-4)",
            "columnGap": "var(--space-4)",
            "lineHeight": "var(--line-height)",
            "letterSpacing": "var(--letter-spacing)",
            "cursor": "default",
            "fontSize": "var(--font-size-2)",
            "--line-height": "var(--line-height-2)",
            "--letter-spacing": "var(--letter-spacing-2)",
            "--checkbox-cards-item-padding-top": "calc(var(--space-4) * 0.875)",
            "--checkbox-cards-item-padding-bottom": "calc(var(--space-4) * 0.875)",
            "--checkbox-cards-item-padding-left": "var(--space-4)",
            "--checkbox-cards-item-border-radius": "var(--radius-3)",
            "--checkbox-cards-item-checkbox-size": "var(--space-4)",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
            "position": {
                "default": "relative",
                "::before": "absolute",
                "::after": "absolute",
            },
            "overflowX": "hidden",
            "overflowY": "hidden",
            "borderRadius": {
                "default": "var(--checkbox-cards-item-border-radius)",
                "::before": "calc(var(--checkbox-cards-item-border-radius) - 1px)",
                "::after": "calc(var(--checkbox-cards-item-border-radius) - 1px)",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "paddingTop": "var(--checkbox-cards-item-padding-top)",
            "paddingRight": "calc(var(--checkbox-cards-item-padding-left) * 2 + var(--checkbox-cards-item-checkbox-size))",
            "paddingBottom": "var(--checkbox-cards-item-padding-bottom)",
            "paddingLeft": "var(--checkbox-cards-item-padding-left)",
            "boxSizing": "border-box",
            "contain": "paint",
            "--inset-border-width": "1px",
            "--inset-border-radius": "var(--checkbox-cards-item-border-radius)",
            "--inset-padding-top": "calc(var(--checkbox-cards-item-padding-top) - 1px)",
            "--inset-padding-right": "calc(calc(var(--checkbox-cards-item-padding-left) * 2 + var(--checkbox-cards-item-checkbox-size)) - 1px)",
            "--inset-padding-bottom": "calc(var(--checkbox-cards-item-padding-bottom) - 1px)",
            "--inset-padding-left": "calc(var(--checkbox-cards-item-padding-left) - 1px)",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": "var(--cursor-button)",
                ":has(:disabled)": "var(--cursor-disabled)",
            },
            "color": {":has(:disabled)": "var(--gray-a9)"},
            "outlineWidth": {
                ":has(:focus-visible)": "2px",
                "::after": {":has(:focus-visible)": "2px"},
            },
            "outlineStyle": {
                ":has(:focus-visible)": "solid",
                "::after": {":has(:focus-visible)": "solid"},
            },
            "outlineColor": {
                ":has(:focus-visible)": "var(--focus-8)",
                "::after": {":has(:focus-visible)": "var(--focus-8)"},
            },
            "outlineOffset": {":has(:focus-visible)": "-1px"},
            "content": {"::before": "''", "::after": "''"},
            "pointerEvents": {"::before": "none", "::after": "none"},
            "transitionProperty": {"::before": "inherit", "::after": "inherit"},
            "transitionDuration": {"::before": "inherit", "::after": "inherit"},
            "transitionTimingFunction": {"::before": "inherit", "::after": "inherit"},
            "transitionDelay": {"::before": "inherit", "::after": "inherit"},
            "top": {"::before": "1px", "::after": "1px"},
            "right": {"::before": "1px", "::after": "1px"},
            "bottom": {"::before": "1px", "::after": "1px"},
            "left": {"::before": "1px", "::after": "1px"},
            "zIndex": {"::before": -1},
            "backgroundColor": {"::before": "var(--color-surface)"},
            "backgroundImage": {
                "::before": {
                    "@media (pointer: coarse)": {
                        ":active:not(:has(:focus-visible), :has(:disabled))": "linear-gradient(var(--gray-a4), var(--gray-a4))"
                    },
                    ":has(:disabled)": "linear-gradient(var(--gray-a2), var(--gray-a2))",
                }
            },
            "boxShadow": {
                "::after": {
                    "default": "0 0 0 1px color-mix(in oklab, var(--gray-a5), var(--gray-5) 25%)",
                    "@media (hover: hover)": {
                        ":hover:not(:has(:disabled))": "0 0 0 1px color-mix(in oklab, var(--gray-a7), var(--gray-7) 25%)"
                    },
                }
            },
            "marginTop": "1px",
            "marginRight": "1px",
            "marginBottom": "1px",
            "marginLeft": "1px",
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
                    ":disabled": "transparent",
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
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "absolute", "::after": "absolute"},
            "right": "var(--checkbox-cards-item-padding-left)",
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": "var(--cursor-checkbox)",
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
            "display": "flex",
            "alignItems": "center",
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
            "position": {
                "default": "relative",
                "::before": "absolute",
                "::after": "absolute",
            },
            "overflowX": "hidden",
            "overflowY": "hidden",
            "borderRadius": {
                "default": "var(--checkbox-cards-item-border-radius)",
                "::before": "calc(var(--checkbox-cards-item-border-radius) - 1px)",
                "::after": "calc(var(--checkbox-cards-item-border-radius) - 1px)",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "paddingTop": "var(--checkbox-cards-item-padding-top)",
            "paddingRight": "calc(var(--checkbox-cards-item-padding-left) * 2 + var(--checkbox-cards-item-checkbox-size))",
            "paddingBottom": "var(--checkbox-cards-item-padding-bottom)",
            "paddingLeft": "var(--checkbox-cards-item-padding-left)",
            "boxSizing": "border-box",
            "contain": "paint",
            "--inset-border-width": "1px",
            "--inset-border-radius": "var(--checkbox-cards-item-border-radius)",
            "--inset-padding-top": "calc(var(--checkbox-cards-item-padding-top) - 1px)",
            "--inset-padding-right": "calc(calc(var(--checkbox-cards-item-padding-left) * 2 + var(--checkbox-cards-item-checkbox-size)) - 1px)",
            "--inset-padding-bottom": "calc(var(--checkbox-cards-item-padding-bottom) - 1px)",
            "--inset-padding-left": "calc(var(--checkbox-cards-item-padding-left) - 1px)",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": "var(--cursor-button)",
                ":has(:disabled)": "var(--cursor-disabled)",
            },
            "color": {":has(:disabled)": "var(--gray-a9)"},
            "outlineWidth": {
                ":has(:focus-visible)": "2px",
                "::after": {":has(:focus-visible)": "2px"},
            },
            "outlineStyle": {
                ":has(:focus-visible)": "solid",
                "::after": {":has(:focus-visible)": "solid"},
            },
            "outlineColor": {
                ":has(:focus-visible)": "var(--focus-8)",
                "::after": {":has(:focus-visible)": "var(--focus-8)"},
            },
            "outlineOffset": {":has(:focus-visible)": "-1px"},
            "content": {"::before": "''", "::after": "''"},
            "pointerEvents": {"::before": "none", "::after": "none"},
            "transitionProperty": {"::before": "inherit", "::after": "inherit"},
            "transitionDuration": {"::before": "inherit", "::after": "inherit"},
            "transitionTimingFunction": {"::before": "inherit", "::after": "inherit"},
            "transitionDelay": {"::before": "inherit", "::after": "inherit"},
            "top": {"::before": "1px", "::after": "1px"},
            "right": {"::before": "1px", "::after": "1px"},
            "bottom": {"::before": "1px", "::after": "1px"},
            "left": {"::before": "1px", "::after": "1px"},
            "zIndex": {"::before": -1},
            "backgroundColor": {"::before": "var(--color-surface)"},
            "backgroundImage": {
                "::before": {
                    "@media (pointer: coarse)": {
                        ":active:not(:has(:focus-visible), :has(:disabled))": "linear-gradient(var(--gray-a4), var(--gray-a4))"
                    },
                    ":has(:disabled)": "linear-gradient(var(--gray-a2), var(--gray-a2))",
                }
            },
            "boxShadow": {
                "::after": {
                    "default": "0 0 0 1px color-mix(in oklab, var(--gray-a5), var(--gray-5) 25%)",
                    "@media (hover: hover)": {
                        ":hover:not(:has(:disabled))": "0 0 0 1px color-mix(in oklab, var(--gray-a7), var(--gray-7) 25%)"
                    },
                }
            },
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
                    ":disabled": "transparent",
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
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "absolute", "::after": "absolute"},
            "right": "var(--checkbox-cards-item-padding-left)",
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": "var(--cursor-checkbox)",
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
    ]


def test_checkbox_cards_classic(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The size, the variant and the contrast of a group are the ones of its cards, and its columns and gap the ones of its grid."""
    component = rx.ui.checkbox_cards.root(
        rx.ui.checkbox_cards.item("One", value="1"),
        name="pick",
        size=rx.breakpoints(initial="1", md="3"),
        variant="classic",
        high_contrast=True,
        color_scheme="ruby",
        columns="2",
        gap="6",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            'className:sx_33c68550fa_c + " " + reflexUIClasses_e201574881',
            'role:"group"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_ec5835b087_c", '"data-rx-cards-item":""'],
                "children": [
                    {"contents": '"One"'},
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_0d82b24940_c",
                            'name:"pick"',
                            'type:"checkbox"',
                            'value:"1"',
                        ],
                        "children": [],
                    },
                ],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "grid",
            "alignItems": "stretch",
            "justifyContent": "flex-start",
            "gridTemplateColumns": "repeat(2, minmax(0, 1fr))",
            "gridTemplateRows": "none",
            "rowGap": "var(--space-6)",
            "columnGap": "var(--space-6)",
            "lineHeight": "var(--line-height)",
            "letterSpacing": "var(--letter-spacing)",
            "cursor": "default",
            "fontSize": {
                "default": "var(--font-size-2)",
                "@media (min-width: 1024px)": "var(--font-size-3)",
            },
            "--line-height": {
                "default": "var(--line-height-2)",
                "@media (min-width: 1024px)": "var(--line-height-3)",
            },
            "--letter-spacing": {
                "default": "var(--letter-spacing-2)",
                "@media (min-width: 1024px)": "var(--letter-spacing-3)",
            },
            "--checkbox-cards-item-padding-top": {
                "default": "calc(var(--space-3) / 1.2)",
                "@media (min-width: 1024px)": "calc(var(--space-5) / 1.2)",
            },
            "--checkbox-cards-item-padding-bottom": {
                "default": "calc(var(--space-3) / 1.2)",
                "@media (min-width: 1024px)": "calc(var(--space-5) / 1.2)",
            },
            "--checkbox-cards-item-padding-left": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "var(--space-5)",
            },
            "--checkbox-cards-item-border-radius": {
                "default": "var(--radius-3)",
                "@media (min-width: 1024px)": "var(--radius-4)",
            },
            "--checkbox-cards-item-checkbox-size": {
                "default": "calc(var(--space-4) * 0.875)",
                "@media (min-width: 1024px)": "calc(var(--space-4) * 1.25)",
            },
        },
        {
            "display": "flex",
            "alignItems": "center",
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
            "position": {
                "default": "relative",
                "::before": "absolute",
                "::after": "absolute",
            },
            "overflowX": "hidden",
            "overflowY": "hidden",
            "borderRadius": {
                "default": "var(--checkbox-cards-item-border-radius)",
                "::before": "calc(var(--checkbox-cards-item-border-radius) - 1px)",
                "::after": "calc(var(--checkbox-cards-item-border-radius) - 1px)",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "paddingTop": "var(--checkbox-cards-item-padding-top)",
            "paddingRight": "calc(var(--checkbox-cards-item-padding-left) * 2 + var(--checkbox-cards-item-checkbox-size))",
            "paddingBottom": "var(--checkbox-cards-item-padding-bottom)",
            "paddingLeft": "var(--checkbox-cards-item-padding-left)",
            "boxSizing": "border-box",
            "contain": "paint",
            "--inset-border-width": "1px",
            "--inset-border-radius": "var(--checkbox-cards-item-border-radius)",
            "--inset-padding-top": "calc(var(--checkbox-cards-item-padding-top) - 1px)",
            "--inset-padding-right": "calc(calc(var(--checkbox-cards-item-padding-left) * 2 + var(--checkbox-cards-item-checkbox-size)) - 1px)",
            "--inset-padding-bottom": "calc(var(--checkbox-cards-item-padding-bottom) - 1px)",
            "--inset-padding-left": "calc(var(--checkbox-cards-item-padding-left) - 1px)",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": "var(--cursor-button)",
                ":has(:disabled)": "var(--cursor-disabled)",
            },
            "color": {":has(:disabled)": "var(--gray-a9)"},
            "outlineWidth": {
                ":has(:focus-visible)": "2px",
                "::after": {":has(:focus-visible)": "2px"},
            },
            "outlineStyle": {
                ":has(:focus-visible)": "solid",
                "::after": {":has(:focus-visible)": "solid"},
            },
            "outlineColor": {
                ":has(:focus-visible)": "var(--focus-8)",
                "::after": {":has(:focus-visible)": "var(--focus-8)"},
            },
            "outlineOffset": {":has(:focus-visible)": "-1px"},
            "content": {"::before": "''", "::after": "''"},
            "pointerEvents": {"::before": "none", "::after": "none"},
            "transitionProperty": {
                "default": "box-shadow",
                "::before": "inherit",
                "::after": "inherit",
            },
            "transitionDuration": {
                "default": "120ms",
                "@media (hover: hover)": {":hover:not(:has(:disabled))": "40ms"},
                "::before": "inherit",
                "::after": "inherit",
            },
            "transitionTimingFunction": {"::before": "inherit", "::after": "inherit"},
            "transitionDelay": {"::before": "inherit", "::after": "inherit"},
            "top": {"::before": "1px", "::after": "1px"},
            "right": {"::before": "1px", "::after": "1px"},
            "bottom": {"::before": "1px", "::after": "1px"},
            "left": {"::before": "1px", "::after": "1px"},
            "zIndex": {"::before": -1},
            "backgroundColor": {"::before": "var(--color-surface)"},
            "backgroundImage": {
                "::before": {
                    "@media (pointer: coarse)": {
                        ":active:not(:has(:focus-visible), :has(:disabled))": "linear-gradient(var(--gray-a4), var(--gray-a4))"
                    },
                    ":has(:disabled)": "linear-gradient(var(--gray-a2), var(--gray-a2))",
                }
            },
            "boxShadow": {
                "default": "var(--rx-if-light, 0 0 0 0 color-mix(in oklab, var(--gray-a3), var(--gray-3) 25%), 0 0 0 0 var(--color-transparent), 0 0 0 0 var(--black-a1), 0 1px 1px -1px var(--gray-a2), 0 2px 1px -2px var(--black-a1), 0 1px 3px -1px var(--black-a1)) var(--rx-if-dark, 0 0 0 0 color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 0 0 0 var(--color-transparent), 0 0 0 0 var(--black-a3), 0 1px 1px -1px var(--black-a6), 0 2px 1px -2px var(--black-a6), 0 1px 3px -1px var(--black-a5))",
                "@media (hover: hover)": {
                    ":hover:not(:has(:disabled))": "var(--rx-if-light, 0 0 0 0 color-mix(in oklab, var(--gray-a4), var(--gray-4) 25%), 0 1px 1px 0 var(--black-a1), 0 2px 1px -2px var(--gray-a3), 0 2px 3px -3px var(--black-a1), 0 3px 12px -5px var(--gray-a3), 0 4px 16px -9px var(--black-a1)) var(--rx-if-dark, 0 0 0 0 color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 0 1px 0 var(--gray-a4), 0 0 1px -2px var(--gray-a4), 0 0 3px -3px var(--gray-a3), 0 0 12px -3px var(--gray-a3), 0 0 16px -9px var(--gray-a7))"
                },
                "::after": {
                    "default": "var(--rx-if-light, 0 0 0 1px color-mix(in oklab, var(--gray-a3), var(--gray-3) 25%), 0 0 0 1px var(--color-transparent), 0 0 0 0.5px var(--black-a1), 0 1px 1px 0 var(--gray-a2), 0 2px 1px -1px var(--black-a1), 0 1px 3px 0 var(--black-a1)) var(--rx-if-dark, 0 0 0 1px color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 0 0 1px var(--color-transparent), 0 0 0 0.5px var(--black-a3), 0 1px 1px 0 var(--black-a6), 0 2px 1px -1px var(--black-a6), 0 1px 3px 0 var(--black-a5))",
                    "@media (hover: hover)": {
                        ":hover:not(:has(:disabled))": "var(--rx-if-light, 0 0 0 1px color-mix(in oklab, var(--gray-a4), var(--gray-4) 25%), 0 1px 1px 1px var(--black-a1), 0 2px 1px -1px var(--gray-a3), 0 2px 3px -2px var(--black-a1), 0 3px 12px -4px var(--gray-a3), 0 4px 16px -8px var(--black-a1)) var(--rx-if-dark, 0 0 0 1px color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 0 1px 1px var(--gray-a4), 0 0 1px -1px var(--gray-a4), 0 0 3px -2px var(--gray-a3), 0 0 12px -2px var(--gray-a3), 0 0 16px -8px var(--gray-a7))"
                    },
                },
            },
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
                    ":is(:checked, :indeterminate):not(:disabled)": "var(--accent-12)",
                    ":disabled": "transparent",
                },
                "::after": {
                    "default": "var(--accent-1)",
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
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "absolute", "::after": "absolute"},
            "right": "var(--checkbox-cards-item-padding-left)",
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": "var(--cursor-checkbox)",
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
            "--checkbox-size": {
                "default": "calc(var(--space-4) * 0.875)",
                "@media (min-width: 1024px)": "calc(var(--space-4) * 1.25)",
            },
            "--checkbox-indicator-size": {
                "default": "calc(9px * var(--scaling))",
                "@media (min-width: 1024px)": "calc(12px * var(--scaling))",
            },
            "--checkbox-border-radius": {
                "default": "calc(var(--radius-1) * 0.875)",
                "@media (min-width: 1024px)": "calc(var(--radius-1) * 1.25)",
            },
            "boxShadow": {
                "::before": {
                    "default": "inset 0 0 0 1px var(--gray-a7)",
                    ":is(:checked, :indeterminate):not(:disabled)": "none",
                    ":disabled": "inset 0 0 0 1px var(--gray-a6)",
                }
            },
        },
    ]


def test_checkbox_cards_bound_to_state(
    ui_plugin: UIPlugin,
):
    """A bound group checks the cards of its value, and a change hands the value over."""
    component = rx.ui.checkbox_cards.root(
        rx.ui.checkbox_cards.item("A", value="a"),
        value=CardsState.picked,
        on_value_change=CardsState.pick,
        name="pick",
        required=True,
        orientation="horizontal",
        loop=True,
        dir="rtl",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_076463c881_c",
            'dir:"rtl"',
            'onChange:((_e) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_checkbox_cards____cards_state.pick", ({ ["picked"] : Array.from(_e.currentTarget.querySelectorAll("input[type=checkbox]:checked")).filter((input) => input.name === _e.target.name).map((input) => input.value) }), ({  })))], [_e], ({  }))))',
            'role:"group"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_12056722ee_c", '"data-rx-cards-item":""'],
                "children": [
                    {"contents": '"A"'},
                    {
                        "name": '"input"',
                        "props": [
                            'checked:(reflex___state____state__tests___units___reflex_components_ui___components___test_checkbox_cards____cards_state.picked_rx_state_.includes("a"))',
                            "className:sx_e9aee32af5_c",
                            'name:"pick"',
                            "readOnly:true",
                            "required:true",
                            'type:"checkbox"',
                            'value:"a"',
                        ],
                        "children": [],
                    },
                ],
            }
        ],
    }


def test_checkbox_cards_unknown_variant(ui_plugin: UIPlugin):
    """A variant a group of cards does not have is an error that lists the ones it has."""
    with pytest.raises(TypeError) as error:
        rx.ui.checkbox_cards.root(variant="soft")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == "Invalid var passed for prop CheckboxCardsRoot.variant, expected type typing.Literal['classic', 'surface'], got value 'soft' of type <class 'str'>."
    )
