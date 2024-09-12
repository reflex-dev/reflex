"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.ivars.base import ImmutableVar

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralSize = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]


class Avatar(RadixThemesComponent):
    """An image element with a fallback for representing the user."""

    tag = "Avatar"

    # The variant of the avatar
    variant: ImmutableVar[Literal["solid", "soft"]]

    # The size of the avatar: "1" - "9"
    size: ImmutableVar[Responsive[LiteralSize]]

    # Color theme of the avatar
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Whether to render the avatar with higher contrast color against background
    high_contrast: ImmutableVar[bool]

    # Override theme radius for avatar: "none" | "small" | "medium" | "large" | "full"
    radius: ImmutableVar[LiteralRadius]

    # The src of the avatar image
    src: ImmutableVar[str]

    # The rendered fallback text
    fallback: ImmutableVar[str]


avatar = Avatar.create
