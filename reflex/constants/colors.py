"""The colors used in Reflex are a wrapper around https://www.radix-ui.com/colors."""
from dataclasses import dataclass
from typing import Literal
from reflex import color_mode_cond

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
    "gray",
]

ShadeType = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]


@dataclass
class Color:
    """A color in the Reflex color palette."""

    # The color palette to use
    color: ColorType

    # The shade of the color to use
    shade: ShadeType = 7

    # Whether to use the alpha variant of the color
    alpha: bool = False

    # The light mode variants of the color
    light: tuple[ColorType, ShadeType, bool] = None

    # The dark mode variants of the color
    dark: tuple[ColorType, ShadeType, bool] = None

    def format_color(self, color: ColorType, shade: ShadeType) -> str:
        """Format a color as a CSS color string."""
        return f"var(--{color}-{'a' if self.alpha else ''}{shade})"

    def __format__(self, format_spec: str) -> str:
        """Format the color as a CSS color string."""

        if self.light and self.dark:
            return color_mode_cond(
                self.format_color(*self.light),
                self.format_color(*self.dark)
            )

        if self.light or self.dark:
            raise ValueError("Both light and dark mode must be specified if you only want to use one shade provide color, shad, and/or alpha directly to rx.color")

        return self.format_color(self.color, self.shade)


