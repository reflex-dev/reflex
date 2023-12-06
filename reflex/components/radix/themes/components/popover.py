"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)


class PopoverRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Popover.Root"

    # The controlled open state of the popover.
    open: Var[bool]

    # The modality of the popover. When set to true, interaction with outside elements will be disabled and only popover content will be visible to screen readers.
    modal: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_open_change": lambda e0: [e0],
        }


class PopoverTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Popover.Trigger"


class PopoverContent(el.Div, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Popover.Content"

    # Size of the button: "1" | "2" | "3" | "4"
    size: Var[Literal[1, 2, 3, 4]]

    # The preferred side of the anchor to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled.
    side: Var[Literal["top", "right", "bottom", "left"]]

    # The distance in pixels from the anchor.
    side_offset: Var[int]

    # The preferred alignment against the anchor. May change when collisions occur.
    align: Var[Literal["start", "center", "end"]]

    # The vertical distance in pixels from the anchor.
    align_offset: Var[int]

    # When true, overrides the side andalign preferences to prevent collisions with boundary edges.
    avoid_collisions: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_open_auto_focus": lambda e0: [e0],
            "on_close_auto_focus": lambda e0: [e0],
            "on_escape_key_down": lambda e0: [e0],
            "on_pointer_down_outside": lambda e0: [e0],
            "on_focus_outside": lambda e0: [e0],
            "on_interact_outside": lambda e0: [e0],
        }


class PopoverClose(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Popover.Close"
