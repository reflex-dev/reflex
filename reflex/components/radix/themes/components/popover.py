"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Optional

from reflex import el
from reflex.components.component import ComponentNamespace
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class PopoverRoot(RadixThemesComponent):
    """Floating element for displaying rich content, triggered by a button."""

    tag: str = "Popover.Root"

    # The controlled open state of the popover.
    open: Optional[Var[bool]] = None

    # The modality of the popover. When set to true, interaction with outside elements will be disabled and only popover content will be visible to screen readers.
    modal: Optional[Var[bool]] = None

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_OPEN_CHANGE: lambda e0: [e0],
        }


class PopoverTrigger(RadixThemesComponent):
    """Wraps the control that will open the popover."""

    tag: str = "Popover.Trigger"


class PopoverContent(el.Div, RadixThemesComponent):
    """Contains content to be rendered in the open popover."""

    tag: str = "Popover.Content"

    # Size of the button: "1" | "2" | "3" | "4"
    size: Optional[Var[Literal["1", "2", "3", "4"]]] = None

    # The preferred side of the anchor to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled.
    side: Optional[Var[Literal["top", "right", "bottom", "left"]]] = None

    # The distance in pixels from the anchor.
    side_offset: Optional[Var[int]] = None

    # The preferred alignment against the anchor. May change when collisions occur.
    align: Optional[Var[Literal["start", "center", "end"]]] = None

    # The vertical distance in pixels from the anchor.
    align_offset: Optional[Var[int]] = None

    # When true, overrides the side andalign preferences to prevent collisions with boundary edges.
    avoid_collisions: Optional[Var[bool]] = None

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


class PopoverClose(RadixThemesComponent):
    """Wraps the control that will close the popover."""

    tag: str = "Popover.Close"


class Popover(ComponentNamespace):
    """Floating element for displaying rich content, triggered by a button."""

    root = staticmethod(PopoverRoot.create)
    trigger = staticmethod(PopoverTrigger.create)
    content = staticmethod(PopoverContent.create)
    close = staticmethod(PopoverClose.create)


popover = Popover()
