"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class Card(elements.Div, RadixThemesComponent):
    """Container that groups related content and actions."""

    tag = "Card"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Card size: "1" - "5"
    size: Var[Responsive[Literal["1", "2", "3", "4", "5"],]]

    # Variant of Card: "solid" | "soft" | "outline" | "ghost"
    variant: Var[Literal["surface", "classic", "ghost"]]


card = Card.create
