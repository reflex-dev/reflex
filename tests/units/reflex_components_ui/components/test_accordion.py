"""Tests for reflex_components_ui.components.accordion."""

import itertools
from collections.abc import Callable
from typing import Any, Literal

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.components import accordion as accordion_module
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


@pytest.fixture(autouse=True)
def ids(monkeypatch: pytest.MonkeyPatch):
    """Number the accordions and the items of each test from one."""
    monkeypatch.setattr(accordion_module, "_ids", itertools.count(1))


def test_accordion(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """An item is a native details: its header is the summary around a heading, and its panel a region the heading names. The root says how the panels move and gives the items their name and their look."""
    component = rx.ui.accordion.root(
        rx.ui.accordion.item(header="One", content="First", value="one"),
        rx.ui.accordion.item(header="Two", content="Second", disabled=True),
        default_value="one",
        variant="outline",
        color_scheme="ruby",
        radius="full",
        duration=100,
        easing="linear",
        dir="rtl",
        id="faq",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            'className:sx_6a0d053193_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_4c7cd6a7ce',
            '"data-rx-accordion":"single"',
            'dir:"rtl"',
            'id:"faq"',
            "onClick:accordionClick",
            "ref:ref_faq",
        ],
        "children": [
            {
                "name": '"details"',
                "props": [
                    'className:"AccordionItem " + sx_563dab9fe8_c',
                    '"data-rx-accordion-item":""',
                    '"data-value":"one"',
                    'name:"rx-accordion-2"',
                    "open:true",
                ],
                "children": [
                    {
                        "name": '"summary"',
                        "props": ['className:"AccordionHeader " + sx_00d40261d7_c'],
                        "children": [
                            {
                                "name": '"h3"',
                                "props": [
                                    'className:"AccordionTrigger " + sx_90f62bd3b2_c',
                                    'id:"rx-accordion-2-trigger-one"',
                                ],
                                "children": [
                                    {"contents": '"One"'},
                                    {
                                        "name": "LucideChevronDown",
                                        "props": [
                                            'className:"AccordionChevron"',
                                            '"data-rx-accordion-icon":""',
                                        ],
                                        "children": [],
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "name": '"div"',
                        "props": [
                            '"aria-labelledby":"rx-accordion-2-trigger-one"',
                            'className:"AccordionContent " + sx_b8a96ba61b_c',
                            'role:"region"',
                        ],
                        "children": [{"contents": '"First"'}],
                    },
                ],
            },
            {
                "name": '"details"',
                "props": [
                    'className:"AccordionItem " + sx_563dab9fe8_c',
                    '"data-rx-accordion-item":""',
                    '"data-value":"rx-accordion-item-1"',
                    'name:"rx-accordion-2"',
                    "open:false",
                ],
                "children": [
                    {
                        "name": '"summary"',
                        "props": [
                            '"aria-disabled":true',
                            'className:"AccordionHeader " + sx_00d40261d7_c',
                            "tabIndex:-1",
                        ],
                        "children": [
                            {
                                "name": '"h3"',
                                "props": [
                                    'className:"AccordionTrigger " + sx_90f62bd3b2_c',
                                    'id:"rx-accordion-2-trigger-rx-accordion-item-1"',
                                ],
                                "children": [
                                    {"contents": '"Two"'},
                                    {
                                        "name": "LucideChevronDown",
                                        "props": [
                                            'className:"AccordionChevron"',
                                            '"data-rx-accordion-icon":""',
                                        ],
                                        "children": [],
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "name": '"div"',
                        "props": [
                            '"aria-labelledby":"rx-accordion-2-trigger-rx-accordion-item-1"',
                            'className:"AccordionContent " + sx_b8a96ba61b_c',
                            'role:"region"',
                        ],
                        "children": [{"contents": '"Second"'}],
                    },
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "borderTopLeftRadius": "var(--radius-4)",
            "borderTopRightRadius": "var(--radius-4)",
            "borderBottomRightRadius": "var(--radius-4)",
            "borderBottomLeftRadius": "var(--radius-4)",
            "boxShadow": "0 2px 10px var(--black-a1)",
            "borderTopWidth": "1px",
            "borderRightWidth": "1px",
            "borderBottomWidth": "1px",
            "borderLeftWidth": "1px",
            "borderTopStyle": "solid",
            "borderRightStyle": "solid",
            "borderBottomStyle": "solid",
            "borderLeftStyle": "solid",
            "borderTopColor": "var(--accent-6)",
            "borderRightColor": "var(--accent-6)",
            "borderBottomColor": "var(--accent-6)",
            "borderLeftColor": "var(--accent-6)",
            "--divider-px": "1px",
            "--animation-duration": "100ms",
            "--animation-easing": "linear",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "width": "100%",
            "marginTop": {"default": "1px", ":first-of-type": "0"},
            "position": {":focus-within": "relative"},
            "zIndex": {":focus-within": 1},
            "--rx-accordion-turn": {"default": "none", "[open]": "rotate(180deg)"},
            "borderTopLeftRadius": {":first-of-type": "var(--radius-4)"},
            "borderTopRightRadius": {":first-of-type": "var(--radius-4)"},
            "borderBottomLeftRadius": {":last-child": "var(--radius-4)"},
            "borderBottomRightRadius": {":last-child": "var(--radius-4)"},
            "borderTopWidth": {"default": "var(--divider-px)", ":first-of-type": "0"},
            "borderTopStyle": {"default": "solid", ":first-of-type": "none"},
            "borderTopColor": {
                "default": "var(--gray-a6)",
                ":first-of-type": "currentcolor",
            },
        },
        {
            "display": {"default": "flex", "::-webkit-details-marker": "none"},
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "listStyleType": "none",
            "pointerEvents": {"[aria-disabled='true']": "none"},
        },
        {
            "boxSizing": "border-box",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": "default",
            "fontSize": "1.1em",
            "fontWeight": "inherit",
            "lineHeight": 1,
            "textAlign": "center",
            "color": "var(--accent-11)",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "flexGrow": 1,
            "flexShrink": 1,
            "flexBasis": "0%",
            "paddingTop": "var(--space-3)",
            "paddingBottom": "var(--space-3)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "width": "100%",
            "backgroundColor": {":hover": "var(--accent-4)"},
            "boxShadow": "0 var(--divider-px) 0 var(--gray-a6)",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "color": "var(--accent-11)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "content": {"::before": "' '", "::after": "' '"},
            "display": {"::before": "block", "::after": "block"},
            "height": {"::before": "var(--space-3)", "::after": "var(--space-3)"},
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "width": "100%",
            "marginTop": {"default": "1px", ":first-of-type": "0"},
            "position": {":focus-within": "relative"},
            "zIndex": {":focus-within": 1},
            "--rx-accordion-turn": {"default": "none", "[open]": "rotate(180deg)"},
            "borderTopLeftRadius": {":first-of-type": "var(--radius-4)"},
            "borderTopRightRadius": {":first-of-type": "var(--radius-4)"},
            "borderBottomLeftRadius": {":last-child": "var(--radius-4)"},
            "borderBottomRightRadius": {":last-child": "var(--radius-4)"},
            "borderTopWidth": {"default": "var(--divider-px)", ":first-of-type": "0"},
            "borderTopStyle": {"default": "solid", ":first-of-type": "none"},
            "borderTopColor": {
                "default": "var(--gray-a6)",
                ":first-of-type": "currentcolor",
            },
        },
        {
            "display": {"default": "flex", "::-webkit-details-marker": "none"},
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "listStyleType": "none",
            "pointerEvents": {"[aria-disabled='true']": "none"},
        },
        {
            "boxSizing": "border-box",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": "default",
            "fontSize": "1.1em",
            "fontWeight": "inherit",
            "lineHeight": 1,
            "textAlign": "center",
            "color": "var(--accent-11)",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "flexGrow": 1,
            "flexShrink": 1,
            "flexBasis": "0%",
            "paddingTop": "var(--space-3)",
            "paddingBottom": "var(--space-3)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "width": "100%",
            "backgroundColor": {":hover": "var(--accent-4)"},
            "boxShadow": "0 var(--divider-px) 0 var(--gray-a6)",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "color": "var(--accent-11)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "content": {"::before": "' '", "::after": "' '"},
            "display": {"::before": "block", "::after": "block"},
            "height": {"::before": "var(--space-3)", "::after": "var(--space-3)"},
        },
    ]


def test_accordion_of_several_needs_no_script(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """An accordion of several items open at once is left to the browser: its items share no name, and nothing hears a press."""
    component = rx.ui.accordion.root(
        rx.ui.accordion.item(
            rx.ui.accordion.trigger("One", id="one"),
            rx.ui.accordion.content("First"),
            value="one",
            variant="ghost",
        ),
        rx.ui.accordion.item(header="Two", content="Second", value="two"),
        type="multiple",
        default_value=["two"],
        variant="soft",
        show_dividers=True,
        disabled=True,
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_9bef01ebc0_c"],
        "children": [
            {
                "name": '"details"',
                "props": [
                    'className:"AccordionItem " + sx_efc06f4e34_c',
                    '"data-rx-accordion-item":""',
                    '"data-value":"one"',
                    "open:false",
                ],
                "children": [
                    {
                        "name": '"summary"',
                        "props": [
                            '"aria-disabled":true',
                            'className:"AccordionHeader " + sx_00d40261d7_c',
                            "tabIndex:-1",
                        ],
                        "children": [
                            {
                                "name": '"h3"',
                                "props": [
                                    'className:"AccordionTrigger " + sx_90f62bd3b2_c',
                                    'id:"one"',
                                    "ref:ref_one",
                                ],
                                "children": [{"contents": '"One"'}],
                            }
                        ],
                    },
                    {
                        "name": '"div"',
                        "props": [
                            '"aria-labelledby":"one"',
                            'className:"AccordionContent " + sx_b8a96ba61b_c',
                            'role:"region"',
                        ],
                        "children": [{"contents": '"First"'}],
                    },
                ],
            },
            {
                "name": '"details"',
                "props": [
                    'className:"AccordionItem " + sx_563dab9fe8_c',
                    '"data-rx-accordion-item":""',
                    '"data-value":"two"',
                    "open:true",
                ],
                "children": [
                    {
                        "name": '"summary"',
                        "props": [
                            '"aria-disabled":true',
                            'className:"AccordionHeader " + sx_00d40261d7_c',
                            "tabIndex:-1",
                        ],
                        "children": [
                            {
                                "name": '"h3"',
                                "props": [
                                    'className:"AccordionTrigger " + sx_90f62bd3b2_c',
                                    'id:"rx-accordion-1-trigger-two"',
                                ],
                                "children": [
                                    {"contents": '"Two"'},
                                    {
                                        "name": "LucideChevronDown",
                                        "props": [
                                            'className:"AccordionChevron"',
                                            '"data-rx-accordion-icon":""',
                                        ],
                                        "children": [],
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "name": '"div"',
                        "props": [
                            '"aria-labelledby":"rx-accordion-1-trigger-two"',
                            'className:"AccordionContent " + sx_b8a96ba61b_c',
                            'role:"region"',
                        ],
                        "children": [{"contents": '"Second"'}],
                    },
                ],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "borderTopLeftRadius": "var(--radius-4)",
            "borderTopRightRadius": "var(--radius-4)",
            "borderBottomRightRadius": "var(--radius-4)",
            "borderBottomLeftRadius": "var(--radius-4)",
            "boxShadow": "0 2px 10px var(--black-a1)",
            "backgroundColor": "var(--accent-3)",
            "--animation-duration": "250ms",
            "--animation-easing": "cubic-bezier(0.87, 0, 0.13, 1)",
            "--divider-px": "1px",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "width": "100%",
            "marginTop": {"default": "1px", ":first-of-type": "0"},
            "position": {":focus-within": "relative"},
            "zIndex": {":focus-within": 1},
            "--rx-accordion-turn": {"default": "none", "[open]": "rotate(180deg)"},
            "borderTopWidth": "var(--divider-px)",
            "borderTopStyle": "solid",
            "borderTopColor": "var(--gray-a6)",
            "borderBottomWidth": {":last-child": "var(--divider-px)"},
            "borderBottomStyle": {":last-child": "solid"},
            "borderBottomColor": {":last-child": "var(--gray-a6)"},
        },
        {
            "display": {"default": "flex", "::-webkit-details-marker": "none"},
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "listStyleType": "none",
            "pointerEvents": {"[aria-disabled='true']": "none"},
        },
        {
            "boxSizing": "border-box",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": "default",
            "fontSize": "1.1em",
            "fontWeight": "inherit",
            "lineHeight": 1,
            "textAlign": "center",
            "color": "var(--accent-11)",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "flexGrow": 1,
            "flexShrink": 1,
            "flexBasis": "0%",
            "paddingTop": "var(--space-3)",
            "paddingBottom": "var(--space-3)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "width": "100%",
            "backgroundColor": {":hover": "var(--accent-4)"},
            "boxShadow": "0 var(--divider-px) 0 var(--gray-a6)",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "color": "var(--accent-11)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "content": {"::before": "' '", "::after": "' '"},
            "display": {"::before": "block", "::after": "block"},
            "height": {"::before": "var(--space-3)", "::after": "var(--space-3)"},
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "width": "100%",
            "marginTop": {"default": "1px", ":first-of-type": "0"},
            "position": {":focus-within": "relative"},
            "zIndex": {":focus-within": 1},
            "--rx-accordion-turn": {"default": "none", "[open]": "rotate(180deg)"},
            "borderTopLeftRadius": {":first-of-type": "var(--radius-4)"},
            "borderTopRightRadius": {":first-of-type": "var(--radius-4)"},
            "borderBottomLeftRadius": {":last-child": "var(--radius-4)"},
            "borderBottomRightRadius": {":last-child": "var(--radius-4)"},
            "borderTopWidth": {"default": "var(--divider-px)", ":first-of-type": "0"},
            "borderTopStyle": {"default": "solid", ":first-of-type": "none"},
            "borderTopColor": {
                "default": "var(--gray-a6)",
                ":first-of-type": "currentcolor",
            },
        },
        {
            "display": {"default": "flex", "::-webkit-details-marker": "none"},
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "listStyleType": "none",
            "pointerEvents": {"[aria-disabled='true']": "none"},
        },
        {
            "boxSizing": "border-box",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": "default",
            "fontSize": "1.1em",
            "fontWeight": "inherit",
            "lineHeight": 1,
            "textAlign": "center",
            "color": "var(--accent-11)",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "flexGrow": 1,
            "flexShrink": 1,
            "flexBasis": "0%",
            "paddingTop": "var(--space-3)",
            "paddingBottom": "var(--space-3)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "width": "100%",
            "backgroundColor": {":hover": "var(--accent-4)"},
            "boxShadow": "0 var(--divider-px) 0 var(--gray-a6)",
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "color": "var(--accent-11)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "content": {"::before": "' '", "::after": "' '"},
            "display": {"::before": "block", "::after": "block"},
            "height": {"::before": "var(--space-3)", "::after": "var(--space-3)"},
        },
    ]


def test_accordion_item_alone(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """An item outside an accordion is one of an accordion without props."""
    component = rx.ui.accordion.item(header="Alone", content="Panel")
    assert component.render() == {
        "name": '"details"',
        "props": [
            'className:"AccordionItem " + sx_aad5443040_c',
            '"data-rx-accordion-item":""',
            '"data-value":"rx-accordion-item-1"',
        ],
        "children": [
            {
                "name": '"summary"',
                "props": ['className:"AccordionHeader " + sx_00d40261d7_c'],
                "children": [
                    {
                        "name": '"h3"',
                        "props": ['className:"AccordionTrigger " + sx_b2de2d1617_c'],
                        "children": [
                            {"contents": '"Alone"'},
                            {
                                "name": "LucideChevronDown",
                                "props": [
                                    'className:"AccordionChevron"',
                                    '"data-rx-accordion-icon":""',
                                ],
                                "children": [],
                            },
                        ],
                    }
                ],
            },
            {
                "name": '"div"',
                "props": [
                    'className:"AccordionContent " + sx_b8a96ba61b_c',
                    'role:"region"',
                ],
                "children": [{"contents": '"Panel"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "width": "100%",
            "marginTop": {"default": "1px", ":first-of-type": "0"},
            "position": {":focus-within": "relative"},
            "zIndex": {":focus-within": 1},
            "--rx-accordion-turn": {"default": "none", "[open]": "rotate(180deg)"},
            "borderTopLeftRadius": {":first-of-type": "var(--radius-4)"},
            "borderTopRightRadius": {":first-of-type": "var(--radius-4)"},
            "borderBottomLeftRadius": {":last-child": "var(--radius-4)"},
            "borderBottomRightRadius": {":last-child": "var(--radius-4)"},
            "borderTopStyle": "none",
        },
        {
            "display": {"default": "flex", "::-webkit-details-marker": "none"},
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "listStyleType": "none",
            "pointerEvents": {"[aria-disabled='true']": "none"},
        },
        {
            "boxSizing": "border-box",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": "default",
            "fontSize": "1.1em",
            "fontWeight": "inherit",
            "lineHeight": 1,
            "textAlign": "center",
            "color": "var(--accent-11)",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "flexGrow": 1,
            "flexShrink": 1,
            "flexBasis": "0%",
            "paddingTop": "var(--space-3)",
            "paddingBottom": "var(--space-3)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "width": "100%",
            "backgroundColor": {":hover": "var(--accent-4)"},
        },
        {
            "overflowX": "hidden",
            "overflowY": "hidden",
            "color": "var(--accent-11)",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "content": {"::before": "' '", "::after": "' '"},
            "display": {"::before": "block", "::after": "block"},
            "height": {"::before": "var(--space-3)", "::after": "var(--space-3)"},
        },
    ]


class AccordionState(rx.State):
    """What an accordion is bound to."""

    open_item: str = "b"
    kind: Literal["classic", "soft", "surface", "outline", "ghost"] = "soft"
    shown: bool = True

    @rx.event
    def set_open(self, value: str | list[str]):
        """Follow the accordion.

        Args:
            value: The value of the open item.
        """
        self.open_item = str(value)


def test_accordion_bound_to_state(ui_plugin: UIPlugin):
    """An accordion bound to state renders its state as expressions, and hands the script what it does on a change."""
    open_item, kind, shown = (
        str(AccordionState.open_item),
        str(AccordionState.kind),
        str(AccordionState.shown),
    )
    component = rx.ui.accordion.root(
        rx.ui.accordion.item(header="A", content="x", value="a"),
        value=AccordionState.open_item,
        on_value_change=AccordionState.set_open,
        variant=AccordionState.kind,
        show_dividers=AccordionState.shown,
        collapsible=True,
    )
    rendered = component.render()
    assert rendered["props"] == [
        f'className:sx_c35f0e8dde_c + " " + (sx_c35f0e8dde_0[{kind}] ?? sx_c35f0e8dde_0d)',
        '"data-bound":""',
        '"data-collapsible":true',
        '"data-rx-accordion":"single"',
        (
            "onClick:((event) => accordionClick(event, ((_value) => (addEvents([(ReflexEvent("
            f'"{AccordionState.get_full_name()}.set_open", ({{ ["value"] : _value }}), '
            "({  })))], [_value], ({  }))))))"
        ),
        f'style:({{ "--v0": (({shown} ? "1px" : "0")) ?? "initial" }})',
    ]
    item = rendered["children"][0]
    assert item["props"] == [
        (
            'className:"AccordionItem " + sx_33774f392f_c + " " + (sx_33774f392f_0['
            f'((["ghost"].includes({kind})) ? "true" : "false")] ?? sx_33774f392f_0d)'
        ),
        '"data-rx-accordion-item":""',
        '"data-value":"a"',
        'name:"rx-accordion-1"',
        f'open:({open_item} === "a")',
    ]
    assert item["children"][0]["children"][0]["props"] == [
        (
            'className:"AccordionTrigger " + sx_631c017a79_c + " " + (sx_631c017a79_0['
            f'((["classic"].includes({kind})) ? "true" : "false")] ?? sx_631c017a79_0d)'
        ),
        'id:"rx-accordion-1-trigger-a"',
    ]


@pytest.mark.parametrize(
    ("props", "scripts"),
    [
        ({}, [ImportVar(tag="accordionClick")]),
        ({"collapsible": True}, None),
        ({"type": "multiple"}, None),
        ({"type": "multiple", "value": ["a"]}, [ImportVar(tag="accordionClick")]),
        (
            {"type": "multiple", "on_value_change": rx.console_log},
            [ImportVar(tag="accordionClick")],
        ),
    ],
)
def test_accordion_loads_its_script_only_for_what_the_browser_does_not_do(
    ui_plugin: UIPlugin, props: dict[str, Any], scripts: list[ImportVar] | None
):
    """A page loads the script of an accordion whose open item stays open, that is bound to state or that says what is open."""
    component = rx.ui.accordion.root(
        rx.ui.accordion.item(header="A", content="x", value="a"), **props
    )
    assert (
        component._get_all_imports().get("$/reflex-ui/behaviors/accordion.js")
        == scripts
    )


def test_accordion_refuses_a_variant_it_does_not_have(ui_plugin: UIPlugin):
    """A variant an accordion does not have fails with the name of the component and its variants."""
    with pytest.raises(StyleError) as error:
        rx.ui.accordion.root(variant="loud")  # pyright: ignore[reportArgumentType]
    assert str(error.value) == (
        'rx.ui.accordion_root: unknown variant "loud". The values are "classic", '
        '"soft", "surface", "outline", "ghost".'
    )
