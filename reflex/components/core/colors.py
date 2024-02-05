"""The colors used in Reflex are a wrapper around https://www.radix-ui.com/colors."""

from reflex.constants.colors import Color, ColorType, ShadeType


def color(
    color: ColorType,
    shade: ShadeType = 7,
    alpha: bool = False,
) -> Color:
    """Create a color object.

    Args:
        color: The color to use.
        shade: The shade of the color to use.
        alpha: Whether to use the alpha variant of the color.

    Returns:
        The color object.
    """
    return Color(color, shade, alpha)
