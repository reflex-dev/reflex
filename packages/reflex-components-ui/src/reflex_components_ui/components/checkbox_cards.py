"""Checkbox cards: a grid of labels, each around a native checkbox."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.components._cards import CardsItem, CardsRoot
from reflex_components_ui.components._group import GroupInput, group_name, has_value
from reflex_components_ui.components.checkbox_group import checked_values_event
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.cards import CHECKBOX_CARDS, CHECKBOX_CARDS_ITEM
from reflex_components_ui.styles.checkbox import (
    CHECKBOX_CARDS_ITEM as CHECKBOX_CARDS_CHECKBOX,
)
from reflex_components_ui.themes import LiteralAccentColor


class CheckboxCardsRoot(CardsRoot):
    """Root element for a CheckboxCards component."""

    styles: ClassVar[ComponentStyles] = CHECKBOX_CARDS

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

    required: Var[bool] = field(
        doc="When true, every card in the group must be checked before the owning form can be submitted."
    )

    orientation: Var[Literal["horizontal", "vertical"]] = field(
        doc="The orientation of the component."
    )

    dir: Var[Literal["ltr", "rtl"]] = field(
        doc="The reading direction of the checkbox cards group. If omitted, inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode."
    )

    loop: Var[bool] = field(
        doc="When true, keyboard navigation will loop from last item to first, and vice versa."
    )

    on_value_change: EventHandler[checked_values_event] = field(
        doc="Fired when the set of checked cards changes."
    )

    _rename_props: ClassVar[dict[str, str]] = {"onValueChange": "onChange"}

    _holds = staticmethod(has_value)

    def _bind(self) -> None:
        """Name the group: a change says which checkboxes it is about by it."""
        self._name = group_name(self.name, "checkbox-cards")

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the group.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of a group.
        """
        return super()._render(props).add_props(role="group")


class CheckboxCardsInput(GroupInput):
    """The checkbox of a card, at its end."""

    styles: ClassVar[ComponentStyles] = CHECKBOX_CARDS_CHECKBOX

    _type: ClassVar[str] = "checkbox"

    value: Var[str] = field(doc="The value given as data when submitted with a name.")

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the checkbox item."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the checkbox item before the owning form can be submitted."
    )

    def _variant_of(self, group: Any) -> str:
        """Get the variant of the checkbox: the same in every card.

        Args:
            group: The group the card is in.

        Returns:
            The variant Radix Themes draws the checkbox of a card in.
        """
        return "surface"


class CheckboxCardsItem(CardsItem):
    """An item in the CheckboxCards component."""

    styles: ClassVar[ComponentStyles] = CHECKBOX_CARDS_ITEM

    _input: ClassVar[type[GroupInput]] = CheckboxCardsInput
    _input_last: ClassVar[bool] = True

    value: Var[str] = field(doc="The value given as data when submitted with a name.")

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the checkbox item."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the checkbox item before the owning form can be submitted."
    )


class CheckboxCards(ComponentNamespace):
    """CheckboxCards components namespace."""

    root = staticmethod(CheckboxCardsRoot.create)
    item = staticmethod(CheckboxCardsItem.create)


checkbox_cards = CheckboxCards()
