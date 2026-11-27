"""Values that differ between the light and the dark appearance."""

from __future__ import annotations

# Set by the base stylesheet wherever an appearance is: the one of the
# current appearance is invalid, the other one is empty.
IF_LIGHT = "--rx-if-light"
IF_DARK = "--rx-if-dark"


def by_appearance(light: str, dark: str) -> str:
    """Write a value that is not a color for both appearances.

    ``light-dark()`` only chooses between colors. This chooses between any
    two values, such as filters or the layers of a shadow, and the computed
    value is the one of the appearance alone.

    Args:
        light: The value in the light appearance.
        dark: The value in the dark appearance.

    Returns:
        The value of a property, or a part of one.
    """
    return f"var({IF_LIGHT}, {light}) var({IF_DARK}, {dark})"
