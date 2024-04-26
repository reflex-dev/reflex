"""Radio component from Radix Themes."""

from types import SimpleNamespace
from typing import Literal, Union

from reflex.vars import Var

from ..base import LiteralAccentColor, RadixThemesComponent


class RadioCardsRoot(RadixThemesComponent):
    """Root element for RadioCards component."""

    tag = "RadioCards.Root"

    # The size of the checkbox cards: "1" | "2" | "3"
    size: Var[Literal["1", "2", "3"]]

    # Variant of button: "classic" | "surface" | "soft"
    variant: Var[Literal["classic", "surface"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Uses a higher contrast color for the component.
    high_contrast: Var[bool]

    # The number of columns:
    columns: Var[Union[str, Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]]]

    # The gap between the checkbox cards:
    gap: Var[Union[str, Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]]]


class RadioCardsItem(RadixThemesComponent):
    """Item element for RadioCards component."""

    tag = "RadioCards.Item"


class RadioCards(SimpleNamespace):
    """RadioCards components namespace."""

    root = staticmethod(RadioCardsRoot.create)
    item = staticmethod(RadioCardsItem.create)


radio_cards = RadioCards()
