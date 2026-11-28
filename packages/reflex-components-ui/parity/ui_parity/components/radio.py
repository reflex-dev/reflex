"""The radio namespace: a group built from a root and its items."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, Matrix

VARIANTS = ["classic", "surface", "soft"]
SIZES = ["1", "2", "3"]
# The first radio button of the group: a button of Radix, an input here.
TARGET = ("button", "input")


def _group(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a radio group from its parts.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the root.

    Returns:
        The group: an item with text, a disabled one, and one alone.
    """
    return namespace.radio.root(
        namespace.radio.item("One", value="1"),
        namespace.radio.item("Two", value="2", disabled=True),
        namespace.radio.item(value="3"),
        **props,
    )


MATRIX = Matrix(
    component="radio",
    render=_group,
    base={"default_value": "1"},
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "default_value": ["2", "3"],
        "color_scheme": ["ruby", "gray"],
        "high_contrast": [True],
        "disabled": [True],
        "appearance": [DARK],
        "state": [HOVER, FOCUS_VISIBLE],
    },
    stage=(160, 110),
    crop="stage",
    target=TARGET,
    parts={
        "root": "[role=radiogroup]",
        "box": ("button::before", "input::before"),
        "dot": ("button::after", "input::after"),
    },
    # Not held to zero. At a threshold of zero the cells that differ do so
    # by where they are on the page: the circle of a radio button and its
    # focus ring are anti-aliased by it. At the default threshold the worst
    # cell differs by 2 pixels.
    tolerance=0.0002,
)
