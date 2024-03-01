"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, List, Literal, Optional

from reflex.components.component import ComponentNamespace
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)


class ContextMenuRoot(RadixThemesComponent):
    """Menu representing a set of actions, displayed at the origin of a pointer right-click or long-press."""

    tag: str = "ContextMenu.Root"

    # The modality of the context menu. When set to true, interaction with outside elements will be disabled and only menu content will be visible to screen readers.
    modal: Optional[Var[bool]] = None

    _invalid_children: List[str] = ["ContextMenuItem"]

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
    """Wraps the element that will open the context menu."""

    tag: str = "ContextMenu.Trigger"

    # Whether the trigger is disabled
    disabled: Optional[Var[bool]] = None

    _valid_parents: List[str] = ["ContextMenuRoot"]

    _invalid_children: List[str] = ["ContextMenuContent"]


class ContextMenuContent(RadixThemesComponent):
    """The component that pops out when the context menu is open."""

    tag: str = "ContextMenu.Content"

    # Button size "1" - "4"
    size: Optional[Var[Literal["1", "2"]]] = None

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Optional[Var[Literal["solid", "soft"]]] = None

    # Override theme color for button
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the button with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # The vertical distance in pixels from the anchor.
    align_offset: Optional[Var[int]] = None

    # When true, overrides the side and aligns preferences to prevent collisions with boundary edges.
    avoid_collisions: Optional[Var[bool]] = None

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
    """Contains all the parts of a submenu."""

    tag: str = "ContextMenu.Sub"


class ContextMenuSubTrigger(RadixThemesComponent):
    """An item that opens a submenu."""

    tag: str = "ContextMenu.SubTrigger"

    # Whether the trigger is disabled
    disabled: Optional[Var[bool]] = None

    _valid_parents: List[str] = ["ContextMenuContent", "ContextMenuSub"]


class ContextMenuSubContent(RadixThemesComponent):
    """The component that pops out when a submenu is open."""

    tag: str = "ContextMenu.SubContent"

    # When true, keyboard navigation will loop from last item to first, and vice versa.
    loop: Optional[Var[bool]] = None

    _valid_parents: List[str] = ["ContextMenuSub"]

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
    """The component that contains the context menu items."""

    tag: str = "ContextMenu.Item"

    # Override theme color for button
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Shortcut to render a menu item as a link
    shortcut: Optional[Var[str]] = None

    _valid_parents: List[str] = ["ContextMenuContent", "ContextMenuSubContent"]


class ContextMenuSeparator(RadixThemesComponent):
    """Separates items in a context menu."""

    tag: str = "ContextMenu.Separator"


class ContextMenu(ComponentNamespace):
    """Menu representing a set of actions, displayed at the origin of a pointer right-click or long-press."""

    root = staticmethod(ContextMenuRoot.create)
    trigger = staticmethod(ContextMenuTrigger.create)
    content = staticmethod(ContextMenuContent.create)
    sub = staticmethod(ContextMenuSub.create)
    sub_trigger = staticmethod(ContextMenuSubTrigger.create)
    sub_content = staticmethod(ContextMenuSubContent.create)
    item = staticmethod(ContextMenuItem.create)
    separator = staticmethod(ContextMenuSeparator.create)


context_menu = ContextMenu()
