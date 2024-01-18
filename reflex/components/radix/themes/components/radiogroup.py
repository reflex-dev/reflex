"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, List, Literal

import reflex as rx
from reflex.components.component import Component
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralSize,
    RadixThemesComponent,
)

LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]


class RadioGroupRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "RadioGroup.Root"

    # The size of the radio group: "1" | "2" | "3"
    size: Var[Literal["1", "2", "3"]]

    # The variant of the radio group
    variant: Var[Literal["classic", "surface", "soft"]]

    # The color of the radio group
    color: Var[LiteralAccentColor]

    # Whether to render the radio group with higher contrast color against background
    high_contrast: Var[bool]

    # The controlled value of the radio item to check. Should be used in conjunction with onValueChange.
    value: Var[str]

    # The initial value of checked radio item. Should be used in conjunction with onValueChange.
    default_value: Var[str]

    # Whether the radio group is disabled
    disabled: Var[bool]

    # The name of the group. Submitted with its owning form as part of a name/value pair.
    name: Var[str]

    # Whether the radio group is required
    required: Var[bool]

    # The orientation of the component.
    orientation: Var[Literal["horizontal", "vertical"]]

    # When true, keyboard navigation will loop from last item to first, and vice versa.
    loop: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_value_change": lambda e0: [e0],
        }


class RadioGroupItem(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "RadioGroup.Item"

    # The value of the radio item to check. Should be used in conjunction with onCheckedChange.
    value: Var[str]

    # When true, prevents the user from interacting with the radio item.
    disabled: Var[bool]

    # When true, indicates that the user must check the radio item before the owning form can be submitted.
    required: Var[bool]


class HighLevelRadioGroup(RadioGroupRoot):
    """High level wrapper for the RadioGroup component."""

    # The items of the radio group.
    items: Var[List[str]]

    # The direction of the radio group.
    direction: Var[LiteralFlexDirection] = Var.create_safe("column")

    # The gap between the items of the radio group.
    gap: Var[LiteralSize] = Var.create_safe("2")

    # The size of the radio group.
    size: Var[Literal["1", "2", "3"]] = Var.create_safe("2")

    @classmethod
    def create(cls, items: Var[List[str]], **props) -> Component:
        """Create a radio group component.

        Args:
            items: The items of the radio group.
            **props: Additional properties to apply to the accordion item.

        Returns:
            The created radio group component.
        """
        direction = props.pop("direction", "column")
        gap = props.pop("gap", "2")
        size = props.pop("size", "2")

        def radio_group_item(value: str) -> Component:
            return Text.create(
                Flex.create(
                    RadioGroupItem.create(value=value),
                    value,
                    gap="2",
                ),
                size=size,
                as_="label",
            )

        if isinstance(items, Var):
            child = [rx.foreach(items, radio_group_item)]
        else:
            child = [radio_group_item(value) for value in items]  #  type: ignore

        return RadioGroupRoot.create(
            Flex.create(
                *child,
                direction=direction,
                gap=gap,
            ),
            size=size,
            **props,
        )
