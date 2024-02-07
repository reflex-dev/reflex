"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)


class DropdownMenuRoot(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "DropdownMenu.Root"

    # The controlled open state of the dropdown menu. Must be used in conjunction with onOpenChange.
    open: Var[bool]

    # The modality of the dropdown menu. When set to true, interaction with outside elements will be disabled and only menu content will be visible to screen readers.
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


class DropdownMenuTrigger(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "DropdownMenu.Trigger"


class DropdownMenuContent(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "DropdownMenu.Content"

    # Dropdown menu size "1" - "2"
    size: Var[Literal["1", "2"]]

    # Variant of dropdown menu: "solid" | "soft" | "outline" | "ghost"
    variant: Var[Literal["solid", "soft"]]

    # Override theme color for dropdown menu
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the dropdown menu with higher contrast color against background
    high_contrast: Var[bool]

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
            EventTriggers.ON_INTERACT_OUTSIDE: lambda e0: [e0],
        }


class DropdownMenuSubTrigger(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "DropdownMenu.SubTrigger"


class DropdownMenuSub(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "DropdownMenu.Sub"


class DropdownMenuSubContent(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "DropdownMenu.SubContent"


class DropdownMenuItem(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "DropdownMenu.Item"

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Shortcut to render a menu item as a link
    shortcut: Var[str]


class DropdownMenuSeparator(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "DropdownMenu.Separator"
