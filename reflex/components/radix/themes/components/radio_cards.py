"""Radio component from Radix Themes."""

from types import SimpleNamespace
from typing import Literal, Union

from reflex.components.core.breakpoints import Responsive
from reflex.event import EventHandler, passthrough_event_spec
from reflex.vars.base import Var

from ..base import LiteralAccentColor, RadixThemesComponent


class RadioCardsRoot(RadixThemesComponent):
    """Root element for RadioCards component."""

    tag = "RadioCards.Root"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # The size of the checkbox cards: "1" | "2" | "3"
    size: Var[Responsive[Literal["1", "2", "3"]]]

    # Variant of button: "classic" | "surface" | "soft"
    variant: Var[Literal["classic", "surface"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Uses a higher contrast color for the component.
    high_contrast: Var[bool]

    # The number of columns:
    columns: Var[
        Responsive[Union[str, Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]]]
    ]

    # The gap between the checkbox cards:
    gap: Var[
        Responsive[Union[str, Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]]]
    ]

    default_value: Var[str]

    # The controlled value of the radio item to check. Should be used in conjunction with onValueChange.
    value: Var[str]

    # The name of the group. Submitted with its owning form as part of a name/value pair.
    name: Var[str]

    # When true, prevents the user from interacting with radio items.
    disabled: Var[bool]

    # When true, indicates that the user must check a radio item before the owning form can be submitted.
    required: Var[bool]

    # The orientation of the component.
    orientation: Var[Literal["horizontal", "vertical", "undefined"]]

    # The reading direction of the radio group. If omitted,
    # inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode.
    dir: Var[Literal["ltr", "rtl"]]

    # When true, keyboard navigation will loop from last item to first, and vice versa.
    loop: Var[bool]

    # Event handler called when the value changes.
    on_value_change: EventHandler[passthrough_event_spec(str)]


class RadioCardsItem(RadixThemesComponent):
    """Item element for RadioCards component."""

    tag = "RadioCards.Item"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # The value given as data when submitted with a name.
    value: Var[str]

    # When true, prevents the user from interacting with the radio item.
    disabled: Var[bool]

    # When true, indicates that the user must check the radio item before the owning form can be submitted.
    required: Var[bool]


class RadioCards(SimpleNamespace):
    """RadioCards components namespace."""

    root = staticmethod(RadioCardsRoot.create)
    item = staticmethod(RadioCardsItem.create)


radio_cards = RadioCards()
