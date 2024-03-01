"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Optional

from reflex import el
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class Card(el.Div, RadixThemesComponent):
    """Container that groups related content and actions."""

    tag: str = "Card"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Card size: "1" - "5"
    size: Optional[Var[Literal["1", "2", "3", "4", "5"]]] = None

    # Variant of Card: "solid" | "soft" | "outline" | "ghost"
    variant: Optional[Var[Literal["surface", "classic", "ghost"]]] = None


card = Card.create
