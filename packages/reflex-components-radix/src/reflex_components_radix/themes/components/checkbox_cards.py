"""Components for the Radix CheckboxCards component."""

from types import SimpleNamespace
from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent


class CheckboxCardsRoot(RadixThemesComponent):
    """Root element for a CheckboxCards component."""

    tag = "CheckboxCards.Root"

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the checkbox cards: "1" | "2" | "3"'
    )

    variant: Var[Literal["classic", "surface"]] = field(
        doc='Variant of button: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Uses a higher contrast color for the component."
    )

    columns: Var[
        Responsive[str | Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]]
    ] = field(doc="The number of columns:")

    gap: Var[Responsive[str | Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]]] = (
        field(doc="The gap between the checkbox cards:")
    )


class CheckboxCardsItem(RadixThemesComponent):
    """An item in the CheckboxCards component."""

    tag = "CheckboxCards.Item"


class CheckboxCards(SimpleNamespace):
    """CheckboxCards components namespace."""

    root = staticmethod(CheckboxCardsRoot.create)
    item = staticmethod(CheckboxCardsItem.create)


checkbox_cards = CheckboxCards()
