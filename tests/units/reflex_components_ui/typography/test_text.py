"""Tests for reflex_components_ui.typography.text."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_text_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Text is a paragraph that follows the size of what is around it."""
    component = rx.ui.text("a")
    assert component.render() == {
        "name": '"p"',
        "props": ["className:sx_af8fa2456e_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
        }
    ]


def test_text_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Its props are styles, and the tag is one of four."""
    component = rx.ui.text(
        "a",
        as_="label",
        size="3",
        weight="bold",
        align="center",
        trim="both",
        id="name",
    )
    assert component.render() == {
        "name": '"label"',
        "props": ["className:sx_82cd5676a1_c", 'id:"name"', "ref:ref_name"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": {
                "default": "0",
                "::after": "calc(var(--leading-trim-end, "
                "var(--default-leading-trim-end)) - var(--line-height, "
                "calc(1em * var(--default-line-height))) / 2)",
            },
            "marginRight": "0",
            "marginBottom": {
                "default": "0",
                "::before": "calc(var(--leading-trim-start, "
                "var(--default-leading-trim-start)) - "
                "var(--line-height, calc(1em * "
                "var(--default-line-height))) / 2)",
            },
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--font-size-3)",
            "--line-height": "var(--line-height-3)",
            "--letter-spacing": "var(--letter-spacing-3)",
            "fontWeight": "var(--font-weight-bold)",
            "textAlign": "center",
            "content": {"::before": "''", "::after": "''"},
            "display": {"::before": "table", "::after": "table"},
            "WebkitTapHighlightColor": {"@media (pointer: coarse)": "transparent"},
            "outlineWidth": {"@media (pointer: coarse)": {":active": "0.75em"}},
            "outlineStyle": {"@media (pointer: coarse)": {":active": "solid"}},
            "outlineColor": {"@media (pointer: coarse)": {":active": "var(--gray-a4)"}},
            "outlineOffset": {"@media (pointer: coarse)": {":active": "-0.6em"}},
        }
    ]


def test_text_fallback_tag(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A tag Radix Themes does not take renders its default, a span."""
    component = rx.ui.text("a", as_="kbd")
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_af8fa2456e_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
        }
    ]


def test_text_color(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A color is the accent of the element, and what the text inside reads."""
    component = rx.ui.text("a", color_scheme="ruby")
    assert component.render() == {
        "name": '"p"',
        "props": ['className:sx_4385ba4ca3_c + " " + reflexUIClasses_e201574881'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "--rx-accent-text": "var(--accent-12)",
            "--rx-accent-link": "var(--accent-12)",
            "--rx-accent-link-line": "underline",
            "--rx-accent-link-line-color": "color-mix(in oklab, var(--accent-a6), "
            "var(--gray-a6))",
            "color": "var(--accent-a11)",
        }
    ]


def test_text_high_contrast(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """High contrast takes its color from the element or from around it."""
    component = rx.ui.box(
        rx.ui.text("a", color_scheme="ruby", high_contrast=True),
        rx.ui.text("b", high_contrast=True),
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_b26ac4fb71_c"],
        "children": [
            {
                "name": '"p"',
                "props": [
                    ('className:sx_ac0c7abea3_c + " " + reflexUIClasses_e201574881')
                ],
                "children": [{"contents": '"a"'}],
            },
            {
                "name": '"p"',
                "props": ["className:sx_2bca64ad62_c"],
                "children": [{"contents": '"b"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {"boxSizing": "border-box", "display": "block"},
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "--rx-accent-text": "var(--accent-12)",
            "color": "var(--accent-12)",
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "color": "var(--rx-accent-text)",
        },
    ]


def test_text_responsive(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A size per breakpoint changes each property at its breakpoint."""
    component = rx.ui.text("a", size=rx.breakpoints(initial="1", sm="3", xl="1"))
    assert component.render() == {
        "name": '"p"',
        "props": ["className:sx_85993688dd_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": {
                "default": "var(--font-size-1)",
                "@media (min-width: 768px)": "var(--font-size-3)",
                "@media (min-width: 1640px)": "var(--font-size-1)",
            },
            "--line-height": {
                "default": "var(--line-height-1)",
                "@media (min-width: 768px)": "var(--line-height-3)",
                "@media (min-width: 1640px)": "var(--line-height-1)",
            },
            "--letter-spacing": {
                "default": "var(--letter-spacing-1)",
                "@media (min-width: 768px)": "var(--letter-spacing-3)",
                "@media (min-width: 1640px)": "var(--letter-spacing-1)",
            },
        }
    ]


def test_text_span(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A span is text that renders a span."""
    component = rx.ui.text.span("a", size="1")
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_6220d7656d_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
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
        }
    ]


def test_text_inline(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Em, strong and quote take their font from the tokens."""
    component = rx.ui.box(
        rx.ui.text.em("a"), rx.ui.text.strong("b"), rx.ui.text.quote("c")
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_b26ac4fb71_c"],
        "children": [
            {
                "name": '"em"',
                "props": ["className:sx_bbfc178e37_c"],
                "children": [{"contents": '"a"'}],
            },
            {
                "name": '"strong"',
                "props": ["className:sx_d0df461b7a_c"],
                "children": [{"contents": '"b"'}],
            },
            {
                "name": '"q"',
                "props": ["className:sx_fd5e021245_c"],
                "children": [{"contents": '"c"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {"boxSizing": "border-box", "display": "block"},
        {
            "fontFamily": "var(--em-font-family)",
            "fontSize": "calc(var(--em-font-size-adjust) * 1em)",
            "fontStyle": "var(--em-font-style)",
            "fontWeight": "var(--em-font-weight)",
            "letterSpacing": "calc(var(--em-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
            "boxSizing": "border-box",
            "lineHeight": "1.25",
            "color": "inherit",
        },
        {
            "fontFamily": "var(--strong-font-family)",
            "fontSize": "calc(var(--strong-font-size-adjust) * 1em)",
            "fontStyle": "var(--strong-font-style)",
            "fontWeight": "var(--strong-font-weight)",
            "letterSpacing": "calc(var(--strong-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
        },
        {
            "fontFamily": "var(--quote-font-family)",
            "fontSize": "calc(var(--quote-font-size-adjust) * 1em)",
            "fontStyle": "var(--quote-font-style)",
            "fontWeight": "var(--quote-font-weight)",
            "letterSpacing": "calc(var(--quote-letter-spacing) + var(--letter-spacing, "
            "var(--default-letter-spacing)))",
            "boxSizing": "border-box",
            "lineHeight": "1.25",
            "color": "inherit",
        },
    ]


def test_kbd_shadow_has_the_layers_of_one_appearance(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """The shadow of a key is the one of Radix Themes in each appearance."""
    [style] = declared_styles(rx.ui.text.kbd("K"))
    assert style["boxShadow"] == (
        "var(--rx-if-light, inset 0 -0.05em 0.5em var(--gray-a2), "
        "inset 0 0.05em var(--white-a12), inset 0 0.25em 0.5em var(--gray-a2), "
        "inset 0 -0.05em var(--gray-a6), 0 0 0 0.05em var(--gray-a5), "
        "0 0.08em 0.17em var(--gray-a7)) "
        "var(--rx-if-dark, inset 0 -0.05em 0.5em var(--gray-a3), "
        "inset 0 0.05em var(--gray-a11), inset 0 0.25em 0.5em var(--gray-a2), "
        "inset 0 -0.1em var(--black-a11), 0 0 0 0.075em var(--gray-a7), "
        "0 0.08em 0.17em var(--black-a12))"
    )
