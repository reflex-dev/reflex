"""The colors used in Reflex are a wrapper around https://www.radix-ui.com/colors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

if TYPE_CHECKING:
    from reflex.vars import Var

ColorType = Literal[
    "gray",
    "mauve",
    "slate",
    "sage",
    "olive",
    "sand",
    "tomato",
    "red",
    "ruby",
    "crimson",
    "pink",
    "plum",
    "purple",
    "violet",
    "iris",
    "indigo",
    "blue",
    "cyan",
    "teal",
    "jade",
    "green",
    "grass",
    "brown",
    "orange",
    "sky",
    "mint",
    "lime",
    "yellow",
    "amber",
    "gold",
    "bronze",
    "accent",
    "black",
    "white",
]

COLORS = frozenset(get_args(ColorType))

ShadeType = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
MIN_SHADE_VALUE = 1
MAX_SHADE_VALUE = 12


def format_color(
    color: ColorType | Var[str], shade: ShadeType | Var[int], alpha: bool | Var[bool]
) -> str:
    """Format a color as a CSS color string.

    Args:
        color: The color to use.
        shade: The shade of the color to use.
        alpha: Whether to use the alpha variant of the color.

    Returns:
        The formatted color.
    """
    if isinstance(alpha, bool):
        return f"var(--{color}-{'a' if alpha else ''}{shade})"

    from reflex.components.core import cond

    alpha_var = cond(alpha, "a", "")
    return f"var(--{color}-{alpha_var}{shade})"


@dataclass
class Color:
    """A color in the Reflex color palette."""

    # The color palette to use
    color: ColorType | Var[str]

    # The shade of the color to use
    shade: ShadeType | Var[int] = 7

    # Whether to use the alpha variant of the color
    alpha: bool | Var[bool] = False

    def __format__(self, format_spec: str) -> str:
        """Format the color as a CSS color string.

        Args:
            format_spec: The format specifier to use.

        Returns:
            The formatted color.
        """
        return format_color(self.color, self.shade, self.alpha)
