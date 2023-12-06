"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralButtonSize = Literal[1, 2, 3, 4]


class SelectRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Root"

    # The size of the select: "1" | "2" | "3"
    size: Var[Literal[1, 2, 3]]

    # The value of the select when initially rendered. Use when you do not need to control the state of the select.
    default_value: Var[str]

    # The controlled value of the select. Use when you need to control the state of the select.
    value: Var[str]

    # The open state of the select when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # The controlled open state of the select. Must be used in conjunction with onOpenChange.
    open: Var[bool]

    # The name of the select control when submitting the form.
    name: Var[str]

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

    # The value of the select item when submitting the form.
    value: Var[str]


class SelectLabel(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Label"


class SelectSeparator(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Separator"
