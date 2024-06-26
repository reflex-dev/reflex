"""Interactive components provided by @radix-ui/themes."""

from typing import List, Literal

from reflex.components.component import ComponentNamespace
from reflex.event import EventHandler
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)


class ContextMenuRoot(RadixThemesComponent):
    """Menu representing a set of actions, displayed at the origin of a pointer right-click or long-press."""

    tag = "ContextMenu.Root"

    # The modality of the context menu. When set to true, interaction with outside elements will be disabled and only menu content will be visible to screen readers.
    modal: Var[bool]

    _invalid_children: List[str] = ["ContextMenuItem"]

    # Fired when the open state changes.
    on_open_change: EventHandler[lambda e0: [e0]]


class ContextMenuTrigger(RadixThemesComponent):
    """Wraps the element that will open the context menu."""

    tag = "ContextMenu.Trigger"

    # Whether the trigger is disabled
    disabled: Var[bool]

    _valid_parents: List[str] = ["ContextMenuRoot"]

    _invalid_children: List[str] = ["ContextMenuContent"]


class ContextMenuContent(RadixThemesComponent):
    """The component that pops out when the context menu is open."""

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

    # When true, overrides the side and aligns preferences to prevent collisions with boundary edges.
    avoid_collisions: Var[bool]

    # Fired when the context menu is closed.
    on_close_auto_focus: EventHandler[lambda e0: [e0]]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[lambda e0: [e0]]

    # Fired when a pointer down event happens outside the context menu.
    on_pointer_down_outside: EventHandler[lambda e0: [e0]]

    # Fired when focus moves outside the context menu.
    on_focus_outside: EventHandler[lambda e0: [e0]]

    # Fired when interacting outside the context menu.
    on_interact_outside: EventHandler[lambda e0: [e0]]


class ContextMenuSub(RadixThemesComponent):
    """Contains all the parts of a submenu."""

    tag = "ContextMenu.Sub"


class ContextMenuSubTrigger(RadixThemesComponent):
    """An item that opens a submenu."""

    tag = "ContextMenu.SubTrigger"

    # Whether the trigger is disabled
    disabled: Var[bool]

    _valid_parents: List[str] = ["ContextMenuContent", "ContextMenuSub"]


class ContextMenuSubContent(RadixThemesComponent):
    """The component that pops out when a submenu is open."""

    tag = "ContextMenu.SubContent"

    # When true, keyboard navigation will loop from last item to first, and vice versa.
    loop: Var[bool]

    _valid_parents: List[str] = ["ContextMenuSub"]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[lambda e0: [e0]]

    # Fired when a pointer down event happens outside the context menu.
    on_pointer_down_outside: EventHandler[lambda e0: [e0]]

    # Fired when focus moves outside the context menu.
    on_focus_outside: EventHandler[lambda e0: [e0]]

    # Fired when interacting outside the context menu.
    on_interact_outside: EventHandler[lambda e0: [e0]]


class ContextMenuItem(RadixThemesComponent):
    """The component that contains the context menu items."""

    tag = "ContextMenu.Item"

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Shortcut to render a menu item as a link
    shortcut: Var[str]

    _valid_parents: List[str] = ["ContextMenuContent", "ContextMenuSubContent"]


class ContextMenuSeparator(RadixThemesComponent):
    """Separates items in a context menu."""

    tag = "ContextMenu.Separator"


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
