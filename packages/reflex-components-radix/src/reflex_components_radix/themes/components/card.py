"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import RadixThemesComponent


class Card(elements.Div, RadixThemesComponent):
    """Container that groups related content and actions."""

    tag = "Card"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[Literal["1", "2", "3", "4", "5"],]] = field(
        doc='Card size: "1" - "5"'
    )

    variant: Var[Literal["surface", "classic", "ghost"]] = field(
        doc='Variant of Card: "surface" | "classic" | "ghost"'
    )


card = Card.create
