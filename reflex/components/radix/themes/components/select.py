"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

import reflex as rx
from reflex.components.component import Component

LiteralButtonSize = Literal[1, 2, 3, 4]


class SelectRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Root"

    # The size of the select: "1" | "2" | "3"
    size: Var[Literal[1, 2, 3]]

    # The value of the select when initially rendered. Use when you do not need to control the state of the select.
    default_value: Var[str]

    # The controlled value of the select. Should be used in conjunction with on_value_change.
    value: Var[str]

    # The open state of the select when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # The controlled open state of the select. Must be used in conjunction with on_open_change.
    open: Var[bool]

    # The name of the select control when submitting the form.
    name: Var[str]

    # When True, prevents the user from interacting with select.
    disabled: Var[bool]

    # When True, indicates that the user must select a value before the owning form can be submitted.
    required: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_open_change": lambda e0: [e0],
            "on_value_change": lambda e0: [e0],
        }


class SelectTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Trigger"

    # Variant of the select trigger
    variant: Var[Literal["classic", "surface", "soft", "ghost"]]

    # The color of the select trigger
    color: Var[LiteralAccentColor]

    # The radius of the select trigger
    radius: Var[LiteralRadius]

    # The placeholder of the select trigger
    placeholder: Var[str]


class SelectContent(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Content"

    # The variant of the select content
    variant: Var[Literal["solid", "soft"]]

    # The color of the select content
    color: Var[LiteralAccentColor]

    # Whether to render the select content with higher contrast color against background
    high_contrast: Var[bool]

    # The positioning mode to use, item-aligned is the default and behaves similarly to a native MacOS menu by positioning content relative to the active item. popper positions content in the same way as our other primitives, for example Popover or DropdownMenu.
    position: Var[Literal["item-aligned", "popper"]]

    # The preferred side of the anchor to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled. Only available when position is set to popper.
    side: Var[Literal["top", "right", "bottom", "left"]]

    # The distance in pixels from the anchor. Only available when position is set to popper.
    side_offset: Var[int]

    # The preferred alignment against the anchor. May change when collisions occur. Only available when position is set to popper.
    align: Var[Literal["start", "center", "end"]]

    # The vertical distance in pixels from the anchor. Only available when position is set to popper.
    align_offset: Var[int]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_close_auto_focus": lambda e0: [e0],
            "on_escape_key_down": lambda e0: [e0],
            "on_pointer_down_outside": lambda e0: [e0],
        }


class SelectGroup(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Group"


class SelectItem(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Item"

    # The value given as data when submitting a form with a name.
    value: Var[str]

    # Whether the select item is disabled
    disabled: Var[bool]


class SelectLabel(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Label"


class SelectSeparator(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Separator"



def select(
        items: Var[list[str]], 
        placeholder: [Var[str] | None] = None, 
        label: [Var[str] | None] = None, 
        color: Var[LiteralAccentColor] = None,
        high_contrast: Var[bool] = None,
        variant: Var[Literal["classic", "surface", "soft", "ghost"]] = None,
        radius: Var[LiteralRadius] = None,
        width: Var[str] = None,
        **props,
        ) -> Component:

    content_props = {}
    if color is not None:
        content_props["color_scheme"] = color
    if high_contrast is not None:
        content_props["high_contrast"] = high_contrast


    trigger_props = {}
    if placeholder is not None:
        trigger_props["placeholder"] = placeholder
    if variant is not None:
        trigger_props["variant"] = variant
    if color is not None:
        trigger_props["color_scheme"] = color
    if radius is not None:
        trigger_props["radius"] = radius
    if width is not None:
        trigger_props["width"] = width


    if isinstance(items, Var):
        child = [rx.foreach(items, lambda item: SelectItem.create(item, value=item))]
    else:
        child = [SelectItem.create(item, value=item) for item in items]


    return SelectRoot.create(
        SelectTrigger.create(
            **trigger_props,
        ),
        SelectContent.create(
            SelectGroup.create(
                SelectLabel.create(label) if label is not None else "",
                *child,
            ),
            **content_props,
        ),
        **props,
    )