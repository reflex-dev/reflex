"""Tests for reflex_components_ui.components.callout."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_callout_from_its_text(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A callout made from its text is a root around an icon and a paragraph."""
    component = rx.ui.callout("Saved.", icon="check")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_91bac2f16e_c", '"data-rx-callout":""'],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_c4b3ee3cc5_c"],
                "children": [{"name": "LucideCheck", "props": [], "children": []}],
            },
            {
                "name": '"p"',
                "props": ["className:sx_9baccc1576_c"],
                "children": [{"contents": '"Saved."'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "grid",
            "alignItems": "flex-start",
            "justifyContent": "flex-start",
            "textAlign": "left",
            "color": "var(--accent-a11)",
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-3)",
            "paddingTop": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "paddingBottom": "var(--space-4)",
            "paddingLeft": "var(--space-4)",
            "borderTopLeftRadius": "var(--radius-4)",
            "borderTopRightRadius": "var(--radius-4)",
            "borderBottomRightRadius": "var(--radius-4)",
            "borderBottomLeftRadius": "var(--radius-4)",
            "--callout-icon-height": "var(--line-height-2)",
            "--rx-callout-font-size": "var(--font-size-2)",
            "--rx-callout-line-height": "var(--line-height-2)",
            "--rx-callout-letter-spacing": "var(--letter-spacing-2)",
            "backgroundColor": "var(--accent-a3)",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "gridColumnStart": "-2",
            "height": "var(--callout-icon-height)",
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--rx-callout-font-size)",
            "--line-height": "var(--rx-callout-line-height)",
            "--letter-spacing": "var(--rx-callout-letter-spacing)",
        },
    ]


def test_callout_without_an_icon(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """Without an icon the text is all the root holds."""
    component = rx.ui.callout(
        "Saved.", variant="outline", size="3", color_scheme="green", high_contrast=True
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            'className:sx_f1fef71f3c_c + " " + reflexUIClasses_e970788578',
            '"data-rx-callout":""',
        ],
        "children": [
            {"name": "Fragment", "props": [], "children": []},
            {
                "name": '"p"',
                "props": ["className:sx_9baccc1576_c"],
                "children": [{"contents": '"Saved."'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "grid",
            "alignItems": "flex-start",
            "justifyContent": "flex-start",
            "textAlign": "left",
            "color": "var(--accent-12)",
            "rowGap": "var(--space-3)",
            "columnGap": "var(--space-4)",
            "paddingTop": "var(--space-5)",
            "paddingRight": "var(--space-5)",
            "paddingBottom": "var(--space-5)",
            "paddingLeft": "var(--space-5)",
            "borderTopLeftRadius": "var(--radius-5)",
            "borderTopRightRadius": "var(--radius-5)",
            "borderBottomRightRadius": "var(--radius-5)",
            "borderBottomLeftRadius": "var(--radius-5)",
            "--callout-icon-height": "var(--line-height-3)",
            "--rx-callout-font-size": "var(--font-size-3)",
            "--rx-callout-line-height": "var(--line-height-3)",
            "--rx-callout-letter-spacing": "var(--letter-spacing-3)",
            "boxShadow": "inset 0 0 0 1px var(--accent-a7)",
            "--rx-accent-text": "var(--accent-12)",
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--rx-callout-font-size)",
            "--line-height": "var(--rx-callout-line-height)",
            "--letter-spacing": "var(--rx-callout-letter-spacing)",
        },
    ]


def test_callout_parts(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The parts follow the size of the root through what it hands down."""
    component = rx.ui.callout.root(
        rx.ui.callout.icon(rx.icon("info")),
        rx.ui.callout.text("Read this."),
        size=rx.breakpoints(initial="1", md="3"),
        variant="surface",
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_06a0a0907d_c", '"data-rx-callout":""'],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_c4b3ee3cc5_c"],
                "children": [{"name": "LucideInfo", "props": [], "children": []}],
            },
            {
                "name": '"p"',
                "props": ["className:sx_9baccc1576_c"],
                "children": [{"contents": '"Read this."'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "grid",
            "alignItems": "flex-start",
            "justifyContent": "flex-start",
            "textAlign": "left",
            "color": "var(--accent-a11)",
            "rowGap": {
                "default": "var(--space-2)",
                "@media (min-width: 1024px)": "var(--space-3)",
            },
            "columnGap": {
                "default": "var(--space-2)",
                "@media (min-width: 1024px)": "var(--space-4)",
            },
            "paddingTop": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "var(--space-5)",
            },
            "paddingRight": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "var(--space-5)",
            },
            "paddingBottom": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "var(--space-5)",
            },
            "paddingLeft": {
                "default": "var(--space-3)",
                "@media (min-width: 1024px)": "var(--space-5)",
            },
            "borderTopLeftRadius": {
                "default": "var(--radius-3)",
                "@media (min-width: 1024px)": "var(--radius-5)",
            },
            "borderTopRightRadius": {
                "default": "var(--radius-3)",
                "@media (min-width: 1024px)": "var(--radius-5)",
            },
            "borderBottomRightRadius": {
                "default": "var(--radius-3)",
                "@media (min-width: 1024px)": "var(--radius-5)",
            },
            "borderBottomLeftRadius": {
                "default": "var(--radius-3)",
                "@media (min-width: 1024px)": "var(--radius-5)",
            },
            "--callout-icon-height": {
                "default": "var(--line-height-2)",
                "@media (min-width: 1024px)": "var(--line-height-3)",
            },
            "--rx-callout-font-size": {
                "default": "var(--font-size-2)",
                "@media (min-width: 1024px)": "var(--font-size-3)",
            },
            "--rx-callout-line-height": {
                "default": "var(--line-height-2)",
                "@media (min-width: 1024px)": "var(--line-height-3)",
            },
            "--rx-callout-letter-spacing": {
                "default": "var(--letter-spacing-2)",
                "@media (min-width: 1024px)": "var(--letter-spacing-3)",
            },
            "boxShadow": "inset 0 0 0 1px var(--accent-a6)",
            "backgroundColor": "var(--accent-a2)",
        },
        {
            "display": "flex",
            "alignItems": "center",
            "gridColumnStart": "-2",
            "height": "var(--callout-icon-height)",
        },
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--rx-callout-font-size)",
            "--line-height": "var(--rx-callout-line-height)",
            "--letter-spacing": "var(--rx-callout-letter-spacing)",
        },
    ]
