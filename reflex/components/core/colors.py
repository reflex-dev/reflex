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
            msg = f"Color must be one of {COLORS}, received {color}"
            raise ValueError(msg)
    elif not isinstance(color, Var):
        msg = "Color must be a string or a Var"
        raise ValueError(msg)

    if isinstance(shade, int):
        if shade < MIN_SHADE_VALUE or shade > MAX_SHADE_VALUE:
            msg = f"Shade must be between {MIN_SHADE_VALUE} and {MAX_SHADE_VALUE}"
            raise ValueError(msg)
    elif not isinstance(shade, Var):
        msg = "Shade must be an integer or a Var"
        raise ValueError(msg)

    if not isinstance(alpha, (bool, Var)):
        msg = "Alpha must be a boolean or a Var"
        raise ValueError(msg)

    return Color(color, shade, alpha)
