"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

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


def radio_group(
    items: [list[str] | Var[list[str]]],
    direction: [str | Var[LiteralFlexDirection]] = "column",
    gap: [str | Var[LiteralSize]] = "2",
    **props
) -> Component:
    """Create a radio group component.

    Args:
        items: The items of the radio group.
        direction: The direction of the radio group.
        gap: The gap between the items of the radio group.
        **props: Additional properties to apply to the accordion item.

    Returns:
        The created radio group component.
    """

    def radio_group_item(value: str) -> Component:
        return Text.create(
            Flex.create(
                RadioGroupItem.create(value=value),
                value,
                gap="2",
            ),
            size="2",
            as_="label",
        )

    if isinstance(items, Var):
        child = [rx.foreach(items, radio_group_item)]
    else:
        child = [radio_group_item(value) for value in items]

    return RadioGroupRoot.create(
        Flex.create(
            *child,
            direction=direction,
            gap=gap,
        ),
        **props,
    )
