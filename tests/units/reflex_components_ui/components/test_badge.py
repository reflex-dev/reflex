"""Tests for reflex_components_ui.components.badge."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


def test_badge_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A badge is a small soft span unless told otherwise."""
    component = rx.ui.badge("New")
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_a19a58d0f6_c"],
        "children": [{"contents": '"New"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "inline-flex",
            "alignItems": "center",
            "whiteSpace": "nowrap",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-medium)",
            "fontStyle": "normal",
            "flexShrink": 0,
            "height": "fit-content",
            "fontSize": "var(--font-size-1)",
            "lineHeight": "var(--line-height-1)",
            "letterSpacing": "var(--letter-spacing-1)",
            "padding": "calc(var(--space-1) * 0.5) calc(var(--space-1) * 1.5)",
            "gap": "calc(var(--space-1) * 1.5)",
            "borderRadius": "max(var(--radius-1), var(--radius-full))",
            "backgroundColor": "var(--accent-a3)",
            "color": "var(--accent-a11)",
        }
    ]


def test_badge_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A solid high-contrast badge with a color and a radius of its own."""
    component = rx.ui.badge(
        "New",
        variant="solid",
        size="3",
        color_scheme="ruby",
        high_contrast=True,
        radius="full",
    )
    assert component.render() == {
        "name": '"span"',
        "props": [
            'className:sx_4faa730ade_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_4c7cd6a7ce'
        ],
        "children": [{"contents": '"New"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "inline-flex",
            "alignItems": "center",
            "whiteSpace": "nowrap",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-medium)",
            "fontStyle": "normal",
            "flexShrink": 0,
            "height": "fit-content",
            "fontSize": "var(--font-size-2)",
            "lineHeight": "var(--line-height-2)",
            "letterSpacing": "var(--letter-spacing-2)",
            "padding": "var(--space-1) calc(var(--space-2) * 1.25)",
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
            "borderRadius": "max(var(--radius-2), var(--radius-full))",
            "backgroundColor": {
                "default": "var(--accent-12)",
                "::selection": "var(--accent-a11)",
            },
            "color": {"default": "var(--accent-1)", "::selection": "var(--accent-1)"},
            "--rx-accent-text": "var(--accent-12)",
            "--rx-accent-link": "var(--accent-12)",
            "--rx-accent-link-line": "underline",
            "--rx-accent-link-line-color": "color-mix(in oklab, var(--accent-a6), var(--gray-a6))",
        }
    ]


def test_badge_responsive(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """The size can change at a breakpoint, under any variant."""
    component = rx.ui.badge(
        "New",
        variant="outline",
        high_contrast=True,
        size=rx.breakpoints(initial="1", md="3"),
    )
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_01ef3af011_c"],
        "children": [{"contents": '"New"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "inline-flex",
            "alignItems": "center",
            "whiteSpace": "nowrap",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-medium)",
            "fontStyle": "normal",
            "flexShrink": 0,
            "height": "fit-content",
            "fontSize": {
                "default": "var(--font-size-1)",
                "@media (min-width: 1024px)": "var(--font-size-2)",
            },
            "lineHeight": {
                "default": "var(--line-height-1)",
                "@media (min-width: 1024px)": "var(--line-height-2)",
            },
            "letterSpacing": {
                "default": "var(--letter-spacing-1)",
                "@media (min-width: 1024px)": "var(--letter-spacing-2)",
            },
            "padding": {
                "default": "calc(var(--space-1) * 0.5) calc(var(--space-1) * 1.5)",
                "@media (min-width: 1024px)": "var(--space-1) calc(var(--space-2) * 1.25)",
            },
            "gap": {
                "default": "calc(var(--space-1) * 1.5)",
                "@media (min-width: 1024px)": "revert-layer",
            },
            "borderRadius": {
                "default": "max(var(--radius-1), var(--radius-full))",
                "@media (min-width: 1024px)": "max(var(--radius-2), var(--radius-full))",
            },
            "boxShadow": "inset 0 0 0 1px var(--accent-a7), inset 0 0 0 1px var(--gray-a11)",
            "color": "var(--accent-12)",
            "rowGap": {"@media (min-width: 1024px)": "var(--space-2)"},
            "columnGap": {"@media (min-width: 1024px)": "var(--space-2)"},
        }
    ]


def test_badge_unknown_variant(ui_plugin: UIPlugin):
    """A variant a badge does not have is an error that lists the ones it has."""
    wrong: dict[str, Any] = {"variant": "ghost"}
    with pytest.raises(StyleError) as error:
        rx.ui.badge("New", **wrong)
    assert str(error.value) == (
        'rx.ui.badge: unknown variant "ghost". '
        'The values are "solid", "soft", "surface", "outline".'
    )
