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
    # Not held to zero, as the matrix of the radio group is not: a circle
    # is anti-aliased by where it is on the page. At the default threshold 7
    # of the 19 cells differ, by at most 49 pixels of 17600.
    tolerance=0.003,
)
