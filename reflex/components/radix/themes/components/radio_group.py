"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, List, Literal, Optional, Union

import reflex as rx
from reflex.components.component import Component, ComponentNamespace
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralSpacing,
    RadixThemesComponent,
)

LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]


class RadioGroupRoot(RadixThemesComponent):
    """A set of interactive radio buttons where only one can be selected at a time."""

    tag: str = "RadioGroup.Root"

    # The size of the radio group: "1" | "2" | "3"
    size: Optional[Var[Literal["1", "2", "3"]]] = None

    # The variant of the radio group
    variant: Optional[Var[Literal["classic", "surface", "soft"]]] = None

    # The color of the radio group
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the radio group with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # The controlled value of the radio item to check. Should be used in conjunction with on_change.
    value: Optional[Var[str]] = None

    # The initial value of checked radio item. Should be used in conjunction with on_change.
    default_value: Optional[Var[str]] = None

    # Whether the radio group is disabled
    disabled: Optional[Var[bool]] = None

    # The name of the group. Submitted with its owning form as part of a name/value pair.
    name: Optional[Var[str]] = None

    # Whether the radio group is required
    required: Optional[Var[bool]] = None

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0],
        }


class RadioGroupItem(RadixThemesComponent):
    """An item in the group that can be checked."""

    tag: str = "RadioGroup.Item"

    # The value of the radio item to check. Should be used in conjunction with on_change.
    value: Optional[Var[str]] = None

    # When true, prevents the user from interacting with the radio item.
    disabled: Optional[Var[bool]] = None

    # When true, indicates that the user must check the radio item before the owning form can be submitted.
    required: Optional[Var[bool]] = None


class HighLevelRadioGroup(RadixThemesComponent):
    """High level wrapper for the RadioGroup component."""

    # The items of the radio group.
    items: Optional[Var[List[str]]] = None

    # The direction of the radio group.
    direction: Optional[Var[LiteralFlexDirection]] = None

    # The gap between the items of the radio group.
    spacing: Var[LiteralSpacing] = Var.create_safe("2")

    # The size of the radio group.
    size: Var[Literal["1", "2", "3"]] = Var.create_safe("2")

    # The variant of the radio group
    variant: Optional[Var[Literal["classic", "surface", "soft"]]] = None

    # The color of the radio group
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the radio group with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # The controlled value of the radio item to check. Should be used in conjunction with on_change.
    value: Optional[Var[str]] = None

    # The initial value of checked radio item. Should be used in conjunction with on_change.
    default_value: Optional[Var[str]] = None

    # Whether the radio group is disabled
    disabled: Optional[Var[bool]] = None

    # The name of the group. Submitted with its owning form as part of a name/value pair.
    name: Optional[Var[str]] = None

    # Whether the radio group is required
    required: Optional[Var[bool]] = None

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    @classmethod
    def create(
        cls,
        items: Var[List[Optional[Union[str, int, float, list, dict, bool]]]],
        **props
    ) -> Component:
        """Create a radio group component.

        Args:
            items: The items of the radio group.
            **props: Additional properties to apply to the accordion item.

        Returns:
            The created radio group component.
        """
        direction = props.pop("direction", "column")
        spacing = props.pop("spacing", "2")
        size = props.pop("size", "2")
        default_value = props.pop("default_value", "")

        # convert only non-strings to json(JSON.stringify) so quotes are not rendered
        # for string literal types.
        if (
            type(default_value) is str
            or isinstance(default_value, Var)
            and default_value._var_type is str
        ):
            default_value = Var.create(default_value, _var_is_string=True)  # type: ignore
        else:
            default_value = (
                Var.create(default_value).to_string()._replace(_var_is_local=False)  # type: ignore
            )

        def radio_group_item(value: str | Var) -> Component:
            item_value = Var.create(value)  # type: ignore
            item_value = rx.cond(
                item_value._type() == str,  # type: ignore
                item_value,
                item_value.to_string()._replace(_var_is_local=False),  # type: ignore
            )._replace(_var_type=str)

            return Text.create(
                Flex.create(
                    RadioGroupItem.create(value=item_value),
                    item_value,
                    spacing="2",
                ),
                size=size,
                as_="label",
            )

        items = Var.create(items)  # type: ignore
        children = [rx.foreach(items, radio_group_item)]

        return RadioGroupRoot.create(
            Flex.create(
                *children,
                direction=direction,
                spacing=spacing,
            ),
            size=size,
            default_value=default_value,
            **props,
        )


class RadioGroup(ComponentNamespace):
    """RadioGroup components namespace."""

    root = staticmethod(RadioGroupRoot.create)
    item = staticmethod(RadioGroupItem.create)
    __call__ = staticmethod(HighLevelRadioGroup.create)


radio = radio_group = RadioGroup()
