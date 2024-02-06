"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)


class ContextMenuRoot(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Root"

    # The modality of the context menu. When set to true, interaction with outside elements will be disabled and only menu content will be visible to screen readers.
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


class ContextMenuTrigger(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Trigger"

    # Whether the trigger is disabled
    disabled: Var[bool]


class ContextMenuContent(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Content"

    # Button size "1" - "4"
    size: Var[Literal["1", "2"]]

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Var[Literal["solid", "soft"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

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
            EventTriggers.ON_CLOSE_AUTO_FOCUS: lambda e0: [e0],
            EventTriggers.ON_ESCAPE_KEY_DOWN: lambda e0: [e0],
            EventTriggers.ON_POINTER_DOWN_OUTSIDE: lambda e0: [e0],
            EventTriggers.ON_FOCUS_OUTSIDE: lambda e0: [e0],
            EventTriggers.ON_INTERACT_OUTSIDE: lambda e0: [e0],
        }


class ContextMenuSub(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Sub"


class ContextMenuSubTrigger(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.SubTrigger"

    # Whether the trigger is disabled
    disabled: Var[bool]


class ContextMenuSubContent(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.SubContent"

    # When true, keyboard navigation will loop from last item to first, and vice versa.
    loop: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_ESCAPE_KEY_DOWN: lambda e0: [e0],
            EventTriggers.ON_POINTER_DOWN_OUTSIDE: lambda e0: [e0],
            EventTriggers.ON_FOCUS_OUTSIDE: lambda e0: [e0],
            EventTriggers.ON_INTERACT_OUTSIDE: lambda e0: [e0],
        }


class ContextMenuItem(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Item"

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Shortcut to render a menu item as a link
    shortcut: Var[str]


class ContextMenuSeparator(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Separator"
