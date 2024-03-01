"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Optional

from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralSize = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]


class Avatar(RadixThemesComponent):
    """An image element with a fallback for representing the user."""

    tag: str = "Avatar"

    # The variant of the avatar
    variant: Optional[Var[Literal["solid", "soft"]]] = None

    # The size of the avatar: "1" - "9"
    size: Optional[Var[LiteralSize]] = None

    # Color theme of the avatar
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the avatar with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # Override theme radius for avatar: "none" | "small" | "medium" | "large" | "full"
    radius: Optional[Var[LiteralRadius]] = None

    # The src of the avatar image
    src: Optional[Var[str]] = None

    # The rendered fallback text
    fallback: Optional[Var[str]] = None


avatar = Avatar.create
