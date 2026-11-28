"""Tests for reflex_components_ui.components.radio_cards."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


class CardsState(rx.State):
    """What a group of cards is bound to."""

    picked: str = "a"

    @rx.event
    def pick(self, picked: str):
        """Follow the group.

        Args:
            picked: What is checked.
        """
        self.picked = picked


def test_radio_cards(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A card is a label around a native input, which the group gives its name, its look and its state."""
    component = rx.ui.radio_cards.root(
        rx.ui.radio_cards.item("One", value="1", id="one", margin="1px"),
        rx.ui.radio_cards.item("Two", value="2", disabled=True),
        default_value="1",
        name="pick",
        id="group",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_a11baf901a_c",
            'id:"group"',
            "ref:ref_group",
            'role:"radiogroup"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_b5ba4311cf_c", '"data-rx-cards-item":""'],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_8e51139181_c",
                            "defaultChecked:true",
                            'id:"one"',
                            'name:"pick"',
                            "ref:ref_one",
                            'type:"radio"',
                            'value:"1"',
                        ],
                        "children": [],
                    },
                    {"contents": '"One"'},
                ],
            },
            {
                "name": '"label"',
                "props": ["className:sx_a4bbfb9e0c_c", '"data-rx-cards-item":""'],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_8e51139181_c",
                            "disabled:true",
                            'name:"pick"',
                            'type:"radio"',
                            'value:"2"',
                        ],
                        "children": [],
                    },
                    {"contents": '"Two"'},
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
            "gridTemplateColumns": "repeat(auto-fit, minmax(160px, 1fr))",
            "gridTemplateRows": "none",
            "rowGap": "var(--space-4)",
            "columnGap": "var(--space-4)",
            "lineHeight": "var(--line-height)",
            "letterSpacing": "var(--letter-spacing)",
            "cursor": "default",
            "fontSize": "var(--font-size-2)",
            "--line-height": "var(--line-height-2)",
            "--letter-spacing": "var(--letter-spacing-2)",
            "--radio-cards-item-padding-x": "var(--space-4)",
            "--radio-cards-item-padding-y": "calc(var(--space-4) * 0.875)",
            "--radio-cards-item-border-radius": "var(--radius-3)",
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
                "default": "var(--radio-cards-item-border-radius)",
                "::before": "calc(var(--radio-cards-item-border-radius) - 1px)",
                "::after": "calc(var(--radio-cards-item-border-radius) - 1px)",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "paddingTop": "var(--radio-cards-item-padding-y)",
            "paddingRight": "var(--radio-cards-item-padding-x)",
            "paddingBottom": "var(--radio-cards-item-padding-y)",
            "paddingLeft": "var(--radio-cards-item-padding-x)",
            "boxSizing": "border-box",
            "contain": "paint",
            "--inset-border-width": "1px",
            "--inset-border-radius": "var(--radio-cards-item-border-radius)",
            "--inset-padding-top": "calc(var(--radio-cards-item-padding-y) - 1px)",
            "--inset-padding-right": "calc(var(--radio-cards-item-padding-x) - 1px)",
            "--inset-padding-bottom": "calc(var(--radio-cards-item-padding-y) - 1px)",
            "--inset-padding-left": "calc(var(--radio-cards-item-padding-x) - 1px)",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": "var(--cursor-button)",
                ":has(:disabled)": "var(--cursor-disabled)",
            },
            "justifyContent": "center",
            "color": {"default": "inherit", ":has(:disabled)": "var(--gray-a9)"},
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
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
                    ":has(:checked):has(:focus-visible)": "linear-gradient(var(--focus-a3), var(--focus-a3))",
                    ":has(:disabled)": "linear-gradient(var(--gray-a2), var(--gray-a2))",
                }
            },
            "outlineOffset": {"::after": "-1px"},
            "outlineStyle": {
                "::after": {":has(:checked)": "solid", ":has(:focus-visible)": "solid"}
            },
            "outlineWidth": {
                "::after": {":has(:checked)": "2px", ":has(:focus-visible)": "2px"}
            },
            "outlineColor": {
                "::after": {
                    ":has(:checked):not(:has(:focus-visible), :has(:disabled))": "var(--accent-indicator)",
                    ":has(:focus-visible):not(:has(:checked))": "var(--focus-8)",
                    ":has(:checked):has(:focus-visible)": "var(--focus-10)",
                    ":has(:disabled)": "var(--gray-8)",
                }
            },
            "boxShadow": {
                "::after": {
                    "default": "0 0 0 1px color-mix(in oklab, var(--gray-a5), var(--gray-5) 25%)",
                    "@media (hover: hover)": {
                        ":hover:not(:has(:checked), :has(:disabled))": "0 0 0 1px color-mix(in oklab, var(--gray-a7), var(--gray-7) 25%)"
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
                "default": "var(--radio-cards-item-border-radius)",
                "::before": "calc(var(--radio-cards-item-border-radius) - 1px)",
                "::after": "calc(var(--radio-cards-item-border-radius) - 1px)",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "paddingTop": "var(--radio-cards-item-padding-y)",
            "paddingRight": "var(--radio-cards-item-padding-x)",
            "paddingBottom": "var(--radio-cards-item-padding-y)",
            "paddingLeft": "var(--radio-cards-item-padding-x)",
            "boxSizing": "border-box",
            "contain": "paint",
            "--inset-border-width": "1px",
            "--inset-border-radius": "var(--radio-cards-item-border-radius)",
            "--inset-padding-top": "calc(var(--radio-cards-item-padding-y) - 1px)",
            "--inset-padding-right": "calc(var(--radio-cards-item-padding-x) - 1px)",
            "--inset-padding-bottom": "calc(var(--radio-cards-item-padding-y) - 1px)",
            "--inset-padding-left": "calc(var(--radio-cards-item-padding-x) - 1px)",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": "var(--cursor-button)",
                ":has(:disabled)": "var(--cursor-disabled)",
            },
            "justifyContent": "center",
            "color": {"default": "inherit", ":has(:disabled)": "var(--gray-a9)"},
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
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
                    ":has(:checked):has(:focus-visible)": "linear-gradient(var(--focus-a3), var(--focus-a3))",
                    ":has(:disabled)": "linear-gradient(var(--gray-a2), var(--gray-a2))",
                }
            },
            "outlineOffset": {"::after": "-1px"},
            "outlineStyle": {
                "::after": {":has(:checked)": "solid", ":has(:focus-visible)": "solid"}
            },
            "outlineWidth": {
                "::after": {":has(:checked)": "2px", ":has(:focus-visible)": "2px"}
            },
            "outlineColor": {
                "::after": {
                    ":has(:checked):not(:has(:focus-visible), :has(:disabled))": "var(--accent-indicator)",
                    ":has(:focus-visible):not(:has(:checked))": "var(--focus-8)",
                    ":has(:checked):has(:focus-visible)": "var(--focus-10)",
                    ":has(:disabled)": "var(--gray-8)",
                }
            },
            "boxShadow": {
                "::after": {
                    "default": "0 0 0 1px color-mix(in oklab, var(--gray-a5), var(--gray-5) 25%)",
                    "@media (hover: hover)": {
                        ":hover:not(:has(:checked), :has(:disabled))": "0 0 0 1px color-mix(in oklab, var(--gray-a7), var(--gray-7) 25%)"
                    },
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
    ]


def test_radio_cards_classic(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The size, the variant and the contrast of a group are the ones of its cards, and its columns and gap the ones of its grid."""
    component = rx.ui.radio_cards.root(
        rx.ui.radio_cards.item("One", value="1"),
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
            'className:sx_ad19158c20_c + " " + reflexUIClasses_e201574881',
            'role:"radiogroup"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_9366874d90_c", '"data-rx-cards-item":""'],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_8e51139181_c",
                            'name:"pick"',
                            'type:"radio"',
                            'value:"1"',
                        ],
                        "children": [],
                    },
                    {"contents": '"One"'},
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
            "--radio-cards-item-padding-x": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "var(--space-5)",
            },
            "--radio-cards-item-padding-y": {
                "default": "calc(var(--space-3) / 1.2)",
                "@media (min-width: 1024px)": "calc(var(--space-5) / 1.2)",
            },
            "--radio-cards-item-border-radius": {
                "default": "var(--radius-3)",
                "@media (min-width: 1024px)": "var(--radius-4)",
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
                "default": "var(--radio-cards-item-border-radius)",
                "::before": "calc(var(--radio-cards-item-border-radius) - 1px)",
                "::after": "calc(var(--radio-cards-item-border-radius) - 1px)",
            },
            "fontFamily": "var(--default-font-family)",
            "fontStyle": "normal",
            "textAlign": "start",
            "paddingTop": "var(--radio-cards-item-padding-y)",
            "paddingRight": "var(--radio-cards-item-padding-x)",
            "paddingBottom": "var(--radio-cards-item-padding-y)",
            "paddingLeft": "var(--radio-cards-item-padding-x)",
            "boxSizing": "border-box",
            "contain": "paint",
            "--inset-border-width": "1px",
            "--inset-border-radius": "var(--radio-cards-item-border-radius)",
            "--inset-padding-top": "calc(var(--radio-cards-item-padding-y) - 1px)",
            "--inset-padding-right": "calc(var(--radio-cards-item-padding-x) - 1px)",
            "--inset-padding-bottom": "calc(var(--radio-cards-item-padding-y) - 1px)",
            "--inset-padding-left": "calc(var(--radio-cards-item-padding-x) - 1px)",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": "var(--cursor-button)",
                ":has(:disabled)": "var(--cursor-disabled)",
            },
            "justifyContent": "center",
            "color": {"default": "inherit", ":has(:disabled)": "var(--gray-a9)"},
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "content": {"::before": "''", "::after": "''"},
            "pointerEvents": {"::before": "none", "::after": "none"},
            "transitionProperty": {
                "default": "box-shadow",
                "::before": "inherit",
                "::after": "inherit",
            },
            "transitionDuration": {
                "default": "120ms",
                "@media (hover: hover)": {
                    ":hover:not(:has(:checked), :has(:disabled))": "40ms"
                },
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
                    ":has(:checked):has(:focus-visible)": "linear-gradient(var(--focus-a3), var(--focus-a3))",
                    ":has(:disabled)": "linear-gradient(var(--gray-a2), var(--gray-a2))",
                }
            },
            "outlineOffset": {"::after": "-1px"},
            "outlineStyle": {
                "::after": {":has(:checked)": "solid", ":has(:focus-visible)": "solid"}
            },
            "outlineWidth": {
                "::after": {":has(:checked)": "2px", ":has(:focus-visible)": "2px"}
            },
            "outlineColor": {
                "::after": {
                    ":has(:checked):not(:has(:focus-visible), :has(:disabled))": "var(--accent-12)",
                    ":has(:focus-visible):not(:has(:checked))": "var(--focus-8)",
                    ":has(:checked):has(:focus-visible)": "var(--focus-10)",
                    ":has(:disabled)": "var(--gray-8)",
                }
            },
            "boxShadow": {
                "default": "var(--rx-if-light, 0 0 0 0 color-mix(in oklab, var(--gray-a3), var(--gray-3) 25%), 0 0 0 0 var(--color-transparent), 0 0 0 0 var(--black-a1), 0 1px 1px -1px var(--gray-a2), 0 2px 1px -2px var(--black-a1), 0 1px 3px -1px var(--black-a1)) var(--rx-if-dark, 0 0 0 0 color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 0 0 0 var(--color-transparent), 0 0 0 0 var(--black-a3), 0 1px 1px -1px var(--black-a6), 0 2px 1px -2px var(--black-a6), 0 1px 3px -1px var(--black-a5))",
                "@media (hover: hover)": {
                    ":hover:not(:has(:checked), :has(:disabled))": "var(--rx-if-light, 0 0 0 0 color-mix(in oklab, var(--gray-a4), var(--gray-4) 25%), 0 1px 1px 0 var(--black-a1), 0 2px 1px -2px var(--gray-a3), 0 2px 3px -3px var(--black-a1), 0 3px 12px -5px var(--gray-a3), 0 4px 16px -9px var(--black-a1)) var(--rx-if-dark, 0 0 0 0 color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 0 1px 0 var(--gray-a4), 0 0 1px -2px var(--gray-a4), 0 0 3px -3px var(--gray-a3), 0 0 12px -3px var(--gray-a3), 0 0 16px -9px var(--gray-a7))"
                },
                "::after": {
                    "default": "var(--rx-if-light, 0 0 0 1px color-mix(in oklab, var(--gray-a3), var(--gray-3) 25%), 0 0 0 1px var(--color-transparent), 0 0 0 0.5px var(--black-a1), 0 1px 1px 0 var(--gray-a2), 0 2px 1px -1px var(--black-a1), 0 1px 3px 0 var(--black-a1)) var(--rx-if-dark, 0 0 0 1px color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 0 0 1px var(--color-transparent), 0 0 0 0.5px var(--black-a3), 0 1px 1px 0 var(--black-a6), 0 2px 1px -1px var(--black-a6), 0 1px 3px 0 var(--black-a5))",
                    "@media (hover: hover)": {
                        ":hover:not(:has(:checked), :has(:disabled))": "var(--rx-if-light, 0 0 0 1px color-mix(in oklab, var(--gray-a4), var(--gray-4) 25%), 0 1px 1px 1px var(--black-a1), 0 2px 1px -1px var(--gray-a3), 0 2px 3px -2px var(--black-a1), 0 3px 12px -4px var(--gray-a3), 0 4px 16px -8px var(--black-a1)) var(--rx-if-dark, 0 0 0 1px color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 0 1px 1px var(--gray-a4), 0 0 1px -1px var(--gray-a4), 0 0 3px -2px var(--gray-a3), 0 0 12px -2px var(--gray-a3), 0 0 16px -8px var(--gray-a7))"
                    },
                },
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
    ]


def test_radio_cards_bound_to_state(
    ui_plugin: UIPlugin,
):
    """A bound group checks the cards of its value, and a change hands the value over."""
    component = rx.ui.radio_cards.root(
        rx.ui.radio_cards.item("A", value="a"),
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
            "className:sx_a11baf901a_c",
            'dir:"rtl"',
            'onChange:((_e) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_radio_cards____cards_state.pick", ({ ["picked"] : _e?.["target"]?.["value"] }), ({  })))], [_e], ({  }))))',
            'role:"radiogroup"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_a4bbfb9e0c_c", '"data-rx-cards-item":""'],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            'checked:(reflex___state____state__tests___units___reflex_components_ui___components___test_radio_cards____cards_state.picked_rx_state_ === "a")',
                            "className:sx_8e51139181_c",
                            'name:"pick"',
                            "readOnly:true",
                            "required:true",
                            'type:"radio"',
                            'value:"a"',
                        ],
                        "children": [],
                    },
                    {"contents": '"A"'},
                ],
            }
        ],
    }


def test_radio_cards_unknown_variant(ui_plugin: UIPlugin):
    """A variant a group of cards does not have is an error that lists the ones it has."""
    with pytest.raises(TypeError) as error:
        rx.ui.radio_cards.root(variant="soft")
    assert (
        str(error.value)
        == "Invalid var passed for prop RadioCardsRoot.variant, expected type typing.Literal['classic', 'surface'], got value 'soft' of type <class 'str'>."
    )
