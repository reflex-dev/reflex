"""Tests for reflex_components_ui.layout.spacer."""

from collections.abc import Callable
from typing import Any

from reflex_base.components.component import Component
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_spacer_compiled(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
    compiled: Callable[[Component], Component],
):
    """A spacer grows to take the room its siblings leave."""
    component = compiled(rx.ui.spacer())
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_a2aca5400f_c"],
        "children": [],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "flex",
            "justifyContent": "flex-start",
            "flex": 1,
            "justifySelf": "stretch",
            "alignSelf": "stretch",
        }
    ]
