"""Interactive components provided by @radix-ui/themes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import reflex as rx
from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import (
    LiteralAccentColor,
    LiteralSpacing,
    RadixThemesComponent,
)
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils import types
from reflex.vars.base import LiteralVar, Var
from reflex.vars.sequence import StringVar

LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]


class RadioGroupRoot(RadixThemesComponent):
    """A set of interactive radio buttons where only one can be selected at a time."""

    tag = "RadioGroup.Root"

    # The size of the radio group: "1" | "2" | "3"
    size: Var[Responsive[Literal["1", "2", "3"]]] = LiteralVar.create("2")

    # The variant of the radio group
    variant: Var[Literal["classic", "surface", "soft"]] = LiteralVar.create("classic")

    # The color of the radio group
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the radio group with higher contrast color against background
    high_contrast: Var[bool]

    # The controlled value of the radio item to check. Should be used in conjunction with on_change.
    value: Var[str]

    # The initial value of checked radio item. Should be used in conjunction with on_change.
    default_value: Var[str]

    # Whether the radio group is disabled
    disabled: Var[bool]

    # The name of the group. Submitted with its owning form as part of a name/value pair.
    name: Var[str]

    # Whether the radio group is required
    required: Var[bool]

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    # Fired when the value of the radio group changes.
    on_change: EventHandler[passthrough_event_spec(str)]


class RadioGroupItem(RadixThemesComponent):
    """An item in the group that can be checked."""

    tag = "RadioGroup.Item"

    # The value of the radio item to check. Should be used in conjunction with on_change.
    value: Var[str]

    # When true, prevents the user from interacting with the radio item.
    disabled: Var[bool]

    # When true, indicates that the user must check the radio item before the owning form can be submitted.
    required: Var[bool]


class HighLevelRadioGroup(RadixThemesComponent):
    """High level wrapper for the RadioGroup component."""

    # The items of the radio group.
    items: Var[Sequence[str]]

    # The direction of the radio group.
    direction: Var[LiteralFlexDirection] = LiteralVar.create("row")

    # The gap between the items of the radio group.
    spacing: Var[LiteralSpacing] = LiteralVar.create("2")

    # The size of the radio group.
    size: Var[Literal["1", "2", "3"]] = LiteralVar.create("2")

    # The variant of the radio group
    variant: Var[Literal["classic", "surface", "soft"]] = LiteralVar.create("classic")

    # The color of the radio group
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the radio group with higher contrast color against background
    high_contrast: Var[bool]

    # The controlled value of the radio item to check. Should be used in conjunction with on_change.
    value: Var[str]

    # The initial value of checked radio item. Should be used in conjunction with on_change.
    default_value: Var[str]

    # Whether the radio group is disabled
    disabled: Var[bool]

    # The name of the group. Submitted with its owning form as part of a name/value pair.
    name: Var[str]

    # Whether the radio group is required
    required: Var[bool]

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    @classmethod
    def create(
        cls,
        items: Var[Sequence[str | int | float | list | dict | bool | None]],
        **props,
    ) -> Component:
        """Create a radio group component.

        Args:
            items: The items of the radio group.
            **props: Additional properties to apply to the accordion item.

        Returns:
            The created radio group component.

        Raises:
            TypeError: If the type of items is invalid.
        """
        direction = props.pop("direction", "row")
        spacing = props.pop("spacing", "2")
        size = props.pop("size", "2")
        variant = props.pop("variant", "classic")
        color_scheme = props.pop("color_scheme", None)
        default_value = props.pop("default_value", "")

        if not isinstance(items, (list, Var)) or (
            isinstance(items, Var) and not types._issubclass(items._var_type, list)
        ):
            items_type = type(items) if not isinstance(items, Var) else items._var_type
            msg = f"The radio group component takes in a list, got {items_type} instead"
            raise TypeError(msg)

        default_value = LiteralVar.create(default_value)

        # convert only non-strings to json(JSON.stringify) so quotes are not rendered
        # for string literal types.
        if isinstance(default_value, str) or (
            isinstance(default_value, Var) and default_value._var_type is str
        ):
            default_value = LiteralVar.create(default_value)
        else:
            default_value = LiteralVar.create(default_value).to_string()

        def radio_group_item(value: Var) -> Component:
            item_value = rx.cond(
                value.js_type() == "string",
                value,
                value.to_string(),
            ).to(StringVar)

            return Text.create(
                Flex.create(
                    RadioGroupItem.create(
                        value=item_value,
                        disabled=props.get("disabled", LiteralVar.create(False)),
                    ),
                    item_value,
                    spacing="2",
                ),
                size=size,
                as_="label",
            )

        children = [
            rx.foreach(
                items,
                radio_group_item,
            )
        ]

        return RadioGroupRoot.create(
            Flex.create(
                *children,
                direction=direction,
                spacing=spacing,
            ),
            size=size,
            variant=variant,
            color_scheme=color_scheme,
            default_value=default_value,
            **props,
        )


class RadioGroup(ComponentNamespace):
    """RadioGroup components namespace."""

    root = staticmethod(RadioGroupRoot.create)
    item = staticmethod(RadioGroupItem.create)
    __call__ = staticmethod(HighLevelRadioGroup.create)


radio = radio_group = RadioGroup()
