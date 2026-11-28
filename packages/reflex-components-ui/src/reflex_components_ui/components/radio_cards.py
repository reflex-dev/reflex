"""Radio cards: a grid of labels, each around a native radio button."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, input_event
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.components._cards import CardsItem, CardsRoot
from reflex_components_ui.components._group import GroupInput, group_name, is_value
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.cards import CARD_INPUT, RADIO_CARDS, RADIO_CARDS_ITEM
from reflex_components_ui.themes import LiteralAccentColor


class RadioCardsRoot(CardsRoot):
    """Root element for RadioCards component."""

    styles: ClassVar[ComponentStyles] = RADIO_CARDS

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

    on_value_change: EventHandler[input_event] = field(
        doc="Event handler called when the value changes."
    )

    _rename_props: ClassVar[dict[str, str]] = {"onValueChange": "onChange"}

    _holds = staticmethod(is_value)

    def _bind(self) -> None:
        """Name the group: the browser takes radio buttons for one by it."""
        self._name = group_name(self.name, "radio-cards")

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the group.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of a group of radio buttons.
        """
        return super()._render(props).add_props(role="radiogroup")


class RadioCardsInput(GroupInput):
    """The radio button of a card, which is not seen."""

    styles: ClassVar[ComponentStyles] = CARD_INPUT

    _type: ClassVar[str] = "radio"

    value: Var[str] = field(doc="The value given as data when submitted with a name.")

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the radio item."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the radio item before the owning form can be submitted."
    )


class RadioCardsItem(CardsItem):
    """Item element for RadioCards component."""

    styles: ClassVar[ComponentStyles] = RADIO_CARDS_ITEM

    _input: ClassVar[type[GroupInput]] = RadioCardsInput

    value: Var[str] = field(doc="The value given as data when submitted with a name.")

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the radio item."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the radio item before the owning form can be submitted."
    )


class RadioCards(ComponentNamespace):
    """RadioCards components namespace."""

    root = staticmethod(RadioCardsRoot.create)
    item = staticmethod(RadioCardsItem.create)


radio_cards = RadioCards()
