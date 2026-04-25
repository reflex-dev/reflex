"""Radio component from Radix Themes."""

from types import SimpleNamespace
from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent


class RadioCardsRoot(RadixThemesComponent):
    """Root element for RadioCards component."""

    tag = "RadioCards.Root"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

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

    default_value: Var[str]

    value: Var[str] = field(
        doc="The controlled value of the radio item to check. Should be used in conjunction with onValueChange."
    )

    name: Var[str] = field(
        doc="The name of the group. Submitted with its owning form as part of a name/value pair."
    )

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with radio items."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check a radio item before the owning form can be submitted."
    )

    orientation: Var[Literal["horizontal", "vertical", "undefined"]] = field(
        doc="The orientation of the component."
    )

    dir: Var[Literal["ltr", "rtl"]] = field(
        doc="The reading direction of the radio group. If omitted, inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode."
    )

    loop: Var[bool] = field(
        doc="When true, keyboard navigation will loop from last item to first, and vice versa."
    )

    on_value_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Event handler called when the value changes."
    )


class RadioCardsItem(RadixThemesComponent):
    """Item element for RadioCards component."""

    tag = "RadioCards.Item"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    value: Var[str] = field(doc="The value given as data when submitted with a name.")

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the radio item."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the radio item before the owning form can be submitted."
    )

    _valid_parents: ClassVar[list[str]] = ["RadioCardsRoot"]


class RadioCards(SimpleNamespace):
    """RadioCards components namespace."""

    root = staticmethod(RadioCardsRoot.create)
    item = staticmethod(RadioCardsItem.create)


radio_cards = RadioCards()
