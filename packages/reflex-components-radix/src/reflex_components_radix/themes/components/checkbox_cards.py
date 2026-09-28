"""Components for the Radix CheckboxCards component."""

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Literal

from reflex_base.components.component import field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent


class CheckboxCardsRoot(RadixThemesComponent):
    """Root element for a CheckboxCards component."""

    tag = "CheckboxCards.Root"
    _is_form_control = True

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

    default_value: Var[Sequence[str]] = field(
        doc="determines which cards, if any, are checked by default."
    )

    value: Var[Sequence[str]] = field(
        doc="The controlled value of the checked cards. Should be used in conjunction with on_value_change."
    )

    name: Var[str] = field(
        doc="The name of the group. Submitted with its owning form as part of a name/value pair."
    )

    disabled: Var[bool] = field(doc="Whether the checkbox cards group is disabled")

    required: Var[bool] = field(doc="Whether the checkbox cards group is required")

    orientation: Var[Literal["horizontal", "vertical"]] = field(
        doc="The orientation of the component."
    )

    dir: Var[Literal["ltr", "rtl"]] = field(
        doc="The reading direction of the checkbox cards group. If omitted, inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode."
    )

    loop: Var[bool] = field(
        doc="When true, keyboard navigation will loop from last item to first, and vice versa."
    )

    on_value_change: EventHandler[passthrough_event_spec(list[str])] = field(
        doc="Fired when the set of checked cards changes."
    )


class CheckboxCardsItem(RadixThemesComponent):
    """An item in the CheckboxCards component."""

    tag = "CheckboxCards.Item"

    value: Var[str] = field(doc="The value given as data when submitted with a name.")

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the checkbox item."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the checkbox item before the owning form can be submitted."
    )


class CheckboxCards(SimpleNamespace):
    """CheckboxCards components namespace."""

    root = staticmethod(CheckboxCardsRoot.create)
    item = staticmethod(CheckboxCardsItem.create)


checkbox_cards = CheckboxCards()
