"""A card: a container that groups related content and actions."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.card import CARD


class Card(UIComponent, elements.Div):
    """Container that groups related content and actions."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = CARD

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
