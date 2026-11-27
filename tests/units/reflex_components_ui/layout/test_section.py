"""Tests for reflex_components_ui.layout.section."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_section_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A section has the space of its default size above and below."""
    component = rx.ui.section("a")
    assert component.render() == {
        "name": '"section"',
        "props": ["className:sx_e51f3ff1bc_c"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "flexShrink": "0",
            "paddingTop": "var(--space-7)",
            "paddingBottom": "var(--space-7)",
        }
    ]


def test_section_sizes(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Each size is a step of the space scale, per breakpoint."""
    component = rx.ui.section(
        "a", size=rx.breakpoints(initial="1", lg="3"), id="pricing"
    )
    assert component.render() == {
        "name": '"section"',
        "props": ["className:sx_ec9b9c5834_c", 'id:"pricing"', "ref:ref_pricing"],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "flexShrink": "0",
            "paddingTop": {
                "default": "var(--space-5)",
                "@media (min-width: 1280px)": "var(--space-9)",
            },
            "paddingBottom": {
                "default": "var(--space-5)",
                "@media (min-width: 1280px)": "var(--space-9)",
            },
        }
    ]
