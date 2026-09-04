"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralSize = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]


class Avatar(RadixThemesComponent):
    """An image element with a fallback for representing the user."""

    tag = "Avatar"

    variant: Var[Literal["solid", "soft"]] = field(doc="The variant of the avatar")

    size: Var[Responsive[LiteralSize]] = field(doc='The size of the avatar: "1" - "9"')

    color_scheme: Var[LiteralAccentColor] = field(doc="Color theme of the avatar")

    high_contrast: Var[bool] = field(
        doc="Whether to render the avatar with higher contrast color against background"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for avatar: "none" | "small" | "medium" | "large" | "full"'
    )

    src: Var[str] = field(doc="The src of the avatar image")

    fallback: Var[str] = field(doc="The rendered fallback text")


avatar = Avatar.create
