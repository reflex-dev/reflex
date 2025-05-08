"""The colors used in Reflex are a wrapper around https://www.radix-ui.com/colors."""

from reflex.constants.base import REFLEX_VAR_OPENING_TAG
from reflex.constants.colors import (
    COLORS,
    MAX_SHADE_VALUE,
    MIN_SHADE_VALUE,
    Color,
    ColorType,
    ShadeType,
)
from reflex.vars.base import Var


def color(
    color: ColorType | Var[str],
    shade: ShadeType | Var[int] = 7,
    alpha: bool | Var[bool] = False,
) -> Color:
    """Create a color object.

    Args:
        color: The color to use.
        shade: The shade of the color to use.
        alpha: Whether to use the alpha variant of the color.

    Returns:
        The color object.

    Raises:
        ValueError: If the color, shade, or alpha are not valid.
    """
    if isinstance(color, str):
        if color not in COLORS and REFLEX_VAR_OPENING_TAG not in color:
            raise ValueError(f"Color must be one of {COLORS}, received {color}")
    elif not isinstance(color, Var):
        raise ValueError("Color must be a string or a Var")

    if isinstance(shade, int):
        if shade < MIN_SHADE_VALUE or shade > MAX_SHADE_VALUE:
            raise ValueError(
                f"Shade must be between {MIN_SHADE_VALUE} and {MAX_SHADE_VALUE}"
            )
    elif not isinstance(shade, Var):
        raise ValueError("Shade must be an integer or a Var")

    if not isinstance(alpha, (bool, Var)):
        raise ValueError("Alpha must be a boolean or a Var")

    return Color(color, shade, alpha)
