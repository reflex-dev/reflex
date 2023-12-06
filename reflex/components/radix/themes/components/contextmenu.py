"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    RadixThemesComponent,
)


class ContextMenuRoot(CommonMarginProps, RadixThemesComponent):
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
            "on_open_change": lambda e0: [e0],
        }


class ContextMenuTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Trigger"

    # Whether the trigger is disabled
    disabled: Var[bool]


class ContextMenuContent(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Content"

    # Button size "1" - "4"
    size: Var[Literal["1", "2"]]

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Var[Literal["solid", "soft"]]

    # Override theme color for button
    color: Var[LiteralAccentColor]

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
            "on_close_auto_focus": lambda e0: [e0],
            "on_escape_key_down": lambda e0: [e0],
            "on_pointer_down_outside": lambda e0: [e0],
            "on_focus_outside": lambda e0: [e0],
            "on_interact_outside": lambda e0: [e0],
        }


class ContextMenuSub(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Sub"


class ContextMenuSubTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.SubTrigger"

    # Whether the trigger is disabled
    disabled: Var[bool]


class ContextMenuSubContent(CommonMarginProps, RadixThemesComponent):
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
            "on_escape_key_down": lambda e0: [e0],
            "on_pointer_down_outside": lambda e0: [e0],
            "on_focus_outside": lambda e0: [e0],
            "on_interact_outside": lambda e0: [e0],
        }


class ContextMenuItem(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Item"

    # Override theme color for button
    color: Var[LiteralAccentColor]

    # Shortcut to render a menu item as a link
    shortcut: Var[str]


class ContextMenuSeparator(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Separator"
