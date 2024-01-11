"""Interactive components provided by @radix-ui/themes."""
from typing import Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    LiteralSize,
    RadixThemesComponent,
)


class Avatar(CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "Avatar"

    # The variant of the avatar
    variant: Var[Literal["solid", "soft"]]

    # The size of the avatar: "1" - "9"
    size: Var[LiteralSize]

    # Color theme of the avatar
    color: Var[LiteralAccentColor]

    # Whether to render the avatar with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for avatar: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]

    # The src of the avatar image
    src: Var[str]

    # The rendered fallback text
    fallback: Var[str]
