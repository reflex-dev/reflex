"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex import el
from reflex.components.component import ComponentNamespace
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
    RadixThemesTriggerComponent,
)


class PopoverRoot(RadixThemesComponent):
    """Floating element for displaying rich content, triggered by a button."""

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
            EventTriggers.ON_OPEN_CHANGE: lambda e0: [e0],
        }


class PopoverTrigger(RadixThemesTriggerComponent):
    """Wraps the control that will open the popover."""

    tag = "Popover.Trigger"


class PopoverContent(el.Div, RadixThemesComponent):
    """Contains content to be rendered in the open popover."""

    tag = "Popover.Content"

    # Size of the button: "1" | "2" | "3" | "4"
    size: Var[Literal["1", "2", "3", "4"]]

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
            EventTriggers.ON_OPEN_AUTO_FOCUS: lambda e0: [e0],
            EventTriggers.ON_CLOSE_AUTO_FOCUS: lambda e0: [e0],
            EventTriggers.ON_ESCAPE_KEY_DOWN: lambda e0: [e0],
            EventTriggers.ON_POINTER_DOWN_OUTSIDE: lambda e0: [e0],
            EventTriggers.ON_FOCUS_OUTSIDE: lambda e0: [e0],
            EventTriggers.ON_INTERACT_OUTSIDE: lambda e0: [e0],
        }


class PopoverClose(RadixThemesTriggerComponent):
    """Wraps the control that will close the popover."""

    tag = "Popover.Close"


class Popover(ComponentNamespace):
    """Floating element for displaying rich content, triggered by a button."""

    root = staticmethod(PopoverRoot.create)
    trigger = staticmethod(PopoverTrigger.create)
    content = staticmethod(PopoverContent.create)
    close = staticmethod(PopoverClose.create)


popover = Popover()
