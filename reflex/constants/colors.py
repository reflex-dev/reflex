"""The colors used in Reflex are a wrapper around https://www.radix-ui.com/colors."""
from dataclasses import dataclass
from typing import Literal

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
