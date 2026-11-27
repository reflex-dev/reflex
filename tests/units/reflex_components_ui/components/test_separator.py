"""Tests for reflex_components_ui.components.separator."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_separator_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A separator is a gray line across its container."""
    component = rx.ui.separator()
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_9af5fbf21f_c"],
        "children": [],
    }
    assert declared_styles(component) == [
        {
            "display": "block",
            "backgroundColor": "var(--gray-a6)",
            "width": "var(--separator-size)",
            "height": "1px",
            "--separator-size": "100%",
        }
    ]


def test_separator_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Its length follows its size in either orientation, and it has a role unless decorative."""
    component = rx.ui.separator(
        size="2", orientation="vertical", color_scheme="ruby", decorative=False
    )
    assert component.render() == {
        "name": '"span"',
        "props": [
            'className:sx_672d983ef5_c + " " + reflexUIClasses_e201574881',
            'role:"separator"',
        ],
        "children": [],
    }
    assert declared_styles(component) == [
        {
            "display": "block",
            "backgroundColor": "var(--accent-a6)",
            "width": "1px",
            "height": "var(--separator-size)",
            "--separator-size": "var(--space-6)",
        }
    ]


def test_separator_responsive(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Both props can change at a breakpoint."""
    component = rx.ui.divider(
        size=rx.breakpoints(initial="1", md="4"),
        orientation=rx.breakpoints(initial="vertical", md="horizontal"),
        decorative=True,
    )
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_3029cc93ff_c"],
        "children": [],
    }
    assert declared_styles(component) == [
        {
            "display": "block",
            "backgroundColor": "var(--gray-a6)",
            "width": {
                "default": "1px",
                "@media (min-width: 1024px)": "var(--separator-size)",
            },
            "height": {
                "default": "var(--separator-size)",
                "@media (min-width: 1024px)": "1px",
            },
            "--separator-size": {
                "default": "var(--space-4)",
                "@media (min-width: 1024px)": "100%",
            },
        }
    ]
