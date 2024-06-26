"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.component import ComponentNamespace
from reflex.components.el import elements
from reflex.event import EventHandler
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

    # Fired when the open state changes.
    on_open_change: EventHandler[lambda e0: [e0]]


class PopoverTrigger(RadixThemesTriggerComponent):
    """Wraps the control that will open the popover."""

    tag = "Popover.Trigger"


class PopoverContent(elements.Div, RadixThemesComponent):
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

    # Fired when the dialog is opened.
    on_open_auto_focus: EventHandler[lambda e0: [e0]]

    # Fired when the dialog is closed.
    on_close_auto_focus: EventHandler[lambda e0: [e0]]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[lambda e0: [e0]]

    # Fired when the pointer is down outside the dialog.
    on_pointer_down_outside: EventHandler[lambda e0: [e0]]

    # Fired when focus moves outside the dialog.
    on_focus_outside: EventHandler[lambda e0: [e0]]

    # Fired when the pointer interacts outside the dialog.
    on_interact_outside: EventHandler[lambda e0: [e0]]


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
