"""Tests for reflex_components_ui.components.radio_group."""

import itertools
from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.components import _group
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


class RadioState(rx.State):
    """What a radio group is bound to."""

    picked: str = "a"
    sizes: list[str] = ["s", "m"]

    @rx.event
    def pick(self, picked: str):
        """Follow the group.

        Args:
            picked: The value of the checked item.
        """
        self.picked = picked


def test_radio_group_from_parts(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The items of a group are native radio buttons with its name, its look and its state; one with children is in a label."""
    component = rx.ui.radio.root(
        rx.ui.radio.item("One", value="1", id="one", margin="1px"),
        rx.ui.radio.item(value="2", disabled=True),
        rx.el.div(rx.ui.radio.item(value="3")),
        default_value="2",
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
            'role:"radiogroup"',
        ],
        "children": [
            {
                "name": '"label"',
                "props": ["className:sx_ab61f35f5f_c"],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_1929c3a89b_c",
                            'id:"one"',
                            'name:"pick"',
                            "ref:ref_one",
                            'type:"radio"',
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
                    "className:sx_1929c3a89b_c",
                    "defaultChecked:true",
                    "disabled:true",
                    'name:"pick"',
                    'type:"radio"',
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
                            "className:sx_1929c3a89b_c",
                            'name:"pick"',
                            'type:"radio"',
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
                    "default": "var(--accent-a4)",
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
                "::before": {":focus-visible": "var(--accent-a8)"},
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
                "default": "var(--cursor-radio)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--radio-size))",
                "::before": "var(--radio-size)",
                "::after": "var(--radio-size)",
            },
            "content": {"::before": "''", "::after": {":checked": "''"}},
            "width": {"::before": "var(--radio-size)", "::after": "var(--radio-size)"},
            "borderTopLeftRadius": {"::before": "100%", "::after": "100%"},
            "borderTopRightRadius": {"::before": "100%", "::after": "100%"},
            "borderBottomRightRadius": {"::before": "100%", "::after": "100%"},
            "borderBottomLeftRadius": {"::before": "100%", "::after": "100%"},
            "pointerEvents": {"::after": "none"},
            "transform": {"::after": "scale(0.4)"},
            "--radio-size": "calc(var(--space-4) * 1.25)",
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
                    "default": "var(--accent-a4)",
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
                "::before": {":focus-visible": "var(--accent-a8)"},
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
                "default": "var(--cursor-radio)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--radio-size))",
                "::before": "var(--radio-size)",
                "::after": "var(--radio-size)",
            },
            "content": {"::before": "''", "::after": {":checked": "''"}},
            "width": {"::before": "var(--radio-size)", "::after": "var(--radio-size)"},
            "borderTopLeftRadius": {"::before": "100%", "::after": "100%"},
            "borderTopRightRadius": {"::before": "100%", "::after": "100%"},
            "borderBottomRightRadius": {"::before": "100%", "::after": "100%"},
            "borderBottomLeftRadius": {"::before": "100%", "::after": "100%"},
            "pointerEvents": {"::after": "none"},
            "transform": {"::after": "scale(0.4)"},
            "--radio-size": "calc(var(--space-4) * 1.25)",
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
                    "default": "var(--accent-a4)",
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
                "::before": {":focus-visible": "var(--accent-a8)"},
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
                "default": "var(--cursor-radio)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--radio-size))",
                "::before": "var(--radio-size)",
                "::after": "var(--radio-size)",
            },
            "content": {"::before": "''", "::after": {":checked": "''"}},
            "width": {"::before": "var(--radio-size)", "::after": "var(--radio-size)"},
            "borderTopLeftRadius": {"::before": "100%", "::after": "100%"},
            "borderTopRightRadius": {"::before": "100%", "::after": "100%"},
            "borderBottomRightRadius": {"::before": "100%", "::after": "100%"},
            "borderBottomLeftRadius": {"::before": "100%", "::after": "100%"},
            "pointerEvents": {"::after": "none"},
            "transform": {"::after": "scale(0.4)"},
            "--radio-size": "calc(var(--space-4) * 1.25)",
        },
    ]


def test_radio_group_classic(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The classic variant, which a group has unless it is given another."""
    component = rx.ui.radio.root(rx.ui.radio.item(value="1"), name="pick")
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
                    ":checked:not(:disabled)": "var(--accent-indicator)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": {
                    "default": "var(--accent-contrast)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    "default": "none",
                    ":checked:not(:disabled)": "linear-gradient(to bottom, var(--white-a3), transparent, var(--black-a3))",
                },
            },
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
                "default": "var(--cursor-radio)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--radio-size))",
                "::before": "var(--radio-size)",
                "::after": "var(--radio-size)",
            },
            "content": {"::before": "''", "::after": {":checked": "''"}},
            "width": {"::before": "var(--radio-size)", "::after": "var(--radio-size)"},
            "borderTopLeftRadius": {"::before": "100%", "::after": "100%"},
            "borderTopRightRadius": {"::before": "100%", "::after": "100%"},
            "borderBottomRightRadius": {"::before": "100%", "::after": "100%"},
            "borderBottomLeftRadius": {"::before": "100%", "::after": "100%"},
            "pointerEvents": {"::after": "none"},
            "transform": {"::after": "scale(0.4)"},
            "--radio-size": "var(--space-4)",
            "boxShadow": {
                "::before": {
                    "default": "inset 0 0 0 1px var(--gray-7), var(--shadow-1)",
                    ":checked:not(:disabled)": "inset 0 0.5px 0.5px var(--white-a4), inset 0 -0.5px 0.5px var(--black-a4)",
                    ":disabled": "var(--shadow-1)",
                }
            },
        },
    ]


def test_radio_group_required_and_disabled(
    ui_plugin: UIPlugin,
):
    """A group that is required or disabled says so on each of its items, and to the accessibility tree."""
    component = rx.ui.radio_group.root(
        rx.ui.radio_group.item(value="1"),
        rx.ui.radio_group.item(value="2", required=False, disabled=False),
        name="pick",
        required=True,
        disabled=True,
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            '"aria-required":true',
            "className:sx_a088d40a93_c",
            'role:"radiogroup"',
        ],
        "children": [
            {
                "name": '"input"',
                "props": [
                    "className:sx_8f60d95144_c",
                    "disabled:true",
                    'name:"pick"',
                    "required:true",
                    'type:"radio"',
                    'value:"1"',
                ],
                "children": [],
            },
            {
                "name": '"input"',
                "props": [
                    "className:sx_8f60d95144_c",
                    "disabled:true",
                    'name:"pick"',
                    "required:true",
                    'type:"radio"',
                    'value:"2"',
                ],
                "children": [],
            },
        ],
    }


def test_radio_group_not_a_list(ui_plugin: UIPlugin):
    """The items of a group are a list."""
    with pytest.raises(TypeError) as error:
        rx.ui.radio("a")
    assert (
        str(error.value)
        == "The radio group component takes in a list, got <class 'str'> instead"
    )


def test_radio_group_unknown_variant(ui_plugin: UIPlugin):
    """A variant a group does not have is an error that lists the ones it has."""
    with pytest.raises(TypeError) as error:
        rx.ui.radio.root(variant="solid")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == "Invalid var passed for prop RadioGroupRoot.variant, expected type typing.Literal['classic', 'surface', 'soft'], got value 'solid' of type <class 'str'>."
    )


def test_radio_group_bound_to_state(ui_plugin: UIPlugin):
    """A bound group checks the item of its value, and a change hands over the value."""
    component = rx.ui.radio.root(
        rx.ui.radio.item(value="a"),
        rx.ui.radio.item(value="b"),
        value=RadioState.picked,
        on_change=RadioState.pick,
        name="pick",
    )
    state = (
        "tests___units___reflex_components_ui___components___test_radio_group"
        "____radio_state"
    )
    picked = f"reflex___state____state__{state}.picked_rx_state_"
    assert component.render() == {
        "name": '"div"',
        "props": [
            "className:sx_a088d40a93_c",
            (
                'onChange:((_e) => (addEvents([(ReflexEvent("reflex___state____state.'
                f'{state}.pick", ({{ ["picked"] : _e?.["target"]?.["value"] }}), '
                "({  })))], [_e], ({  }))))"
            ),
            'role:"radiogroup"',
        ],
        "children": [
            {
                "name": '"input"',
                "props": [
                    f'checked:({picked} === "{value}")',
                    "className:sx_8f60d95144_c",
                    'name:"pick"',
                    "readOnly:true",
                    'type:"radio"',
                    f'value:"{value}"',
                ],
                "children": [],
            }
            for value in ("a", "b")
        ],
    }
    # The compiler finds the state an item reads through its group.
    item = component.children[0]
    assert [str(var) for var in item._get_vars()] == [  # pyright: ignore[reportAttributeAccessIssue]
        '"a"',
        '"pick"',
        f'({picked} === "a")',
    ]


def test_radio_group_without_a_name(
    ui_plugin: UIPlugin, monkeypatch: pytest.MonkeyPatch
):
    """Each group without a name is given one of its own: it is what groups its items."""
    monkeypatch.setattr(_group, "_names", itertools.count(7))
    names = [
        [item.render()["props"][1] for item in group.children]
        for group in (
            rx.ui.radio.root(rx.ui.radio.item(value="1"), rx.ui.radio.item(value="2")),
            rx.ui.radio.root(rx.ui.radio.item(value="1")),
        )
    ]
    assert names == [
        ['name:"rx-radio-7"', 'name:"rx-radio-7"'],
        ['name:"rx-radio-8"'],
    ]


def test_radio_group_inside_another(ui_plugin: UIPlugin):
    """The items below another group are the ones of that group."""
    inner = rx.ui.radio.root(rx.ui.radio.item(value="1"), name="inner", size="1")
    rx.ui.radio.root(rx.ui.radio.item(value="2"), inner, name="outer", size="3")
    item = inner.children[0]
    assert item._group == {"name": inner.name}  # pyright: ignore[reportAttributeAccessIssue]
    assert item._element_styles().style.style["--radio-size"] == (  # pyright: ignore[reportAttributeAccessIssue]
        "calc(var(--space-4) * 0.875)"
    )


def test_radio_group_from_items(ui_plugin: UIPlugin):
    """A list of items is a row of labels, each around a radio button of the group."""
    component = rx.ui.radio(
        ["a", "b"], default_value="a", name="pick", direction="column", spacing="4"
    )
    rendered = component.render()
    items = rendered["children"][0]["children"][0]
    items["iterable"] = str(items["iterable"])
    value = (
        '(((typeof(value_rx_state_))?.valueOf?.() === "string"?.valueOf?.()) ? '
        "value_rx_state_ : (JSON.stringify(value_rx_state_)))"
    )
    index = "index_cb46f9c6d80243188763ec1eabe9a266"
    assert rendered == {
        "name": '"div"',
        "props": ["className:sx_a088d40a93_c", 'role:"radiogroup"'],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_29f00bc870_c"],
                "children": [
                    {
                        "name": "",
                        "props": [],
                        "children": [
                            {
                                "name": '"label"',
                                "props": ["className:sx_d1083f6dbf_c", f"key:{index}"],
                                "children": [
                                    {
                                        "name": '"div"',
                                        "props": ["className:sx_1362d43b5f_c"],
                                        "children": [
                                            {
                                                "name": '"input"',
                                                "props": [
                                                    "className:sx_8f60d95144_c",
                                                    f'defaultChecked:("a" === {value})',
                                                    "disabled:false",
                                                    'name:"pick"',
                                                    'type:"radio"',
                                                    f"value:{value}",
                                                ],
                                                "children": [],
                                            },
                                            {"contents": value},
                                        ],
                                    }
                                ],
                            }
                        ],
                        "iterable": '["a", "b"]',
                        "arg_var_name": "value_rx_state_",
                        "index_var_name": index,
                        "iterable_state": '["a", "b"]',
                        "arg_name": "value_rx_state_",
                        "arg_index": index,
                    }
                ],
            }
        ],
    }
