"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)

LiteralSize = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]


class Avatar(RadixThemesComponent):
    """An image element with a fallback for representing the user."""

    # The size of the avatar: "1" - "9"
    size: Var[Responsive[LiteralSize]]


avatar = Avatar.create
