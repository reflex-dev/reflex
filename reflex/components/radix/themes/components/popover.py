"""Interactive components provided by @radix-ui/themes."""

from typing import Dict, Literal, Union

from reflex.components.component import ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex.vars.base import Var

from ..base import RadixThemesComponent, RadixThemesTriggerComponent


class PopoverRoot(RadixThemesComponent):
    """Floating element for displaying rich content, triggered by a button."""

    tag = "Popover.Root"

    # The controlled open state of the popover.
    open: Var[bool]

    # The modality of the popover. When set to true, interaction with outside elements will be disabled and only popover content will be visible to screen readers.
    modal: Var[bool]

    # Fired when the open state changes.
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # The open state of the popover when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]


class PopoverTrigger(RadixThemesTriggerComponent):
    """Wraps the control that will open the popover."""

    tag = "Popover.Trigger"


class PopoverContent(elements.Div, RadixThemesComponent):
    """Contains content to be rendered in the open popover."""

    tag = "Popover.Content"

    # Size of the button: "1" | "2" | "3" | "4"
    size: Var[Responsive[Literal["1", "2", "3", "4"]]]

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

    # The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { "top": 20, "left": 20 }. Defaults to 0.
    collision_padding: Var[Union[float, int, Dict[str, Union[float, int]]]]

    # The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless. Defaults to "partial".
    sticky: Var[Literal["partial", "always"]]

    # Whether to hide the content when the trigger becomes fully occluded. Defaults to False.
    hide_when_detached: Var[bool]

    # Fired when the dialog is opened.
    on_open_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the dialog is closed.
    on_close_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[no_args_event_spec]

    # Fired when the pointer is down outside the dialog.
    on_pointer_down_outside: EventHandler[no_args_event_spec]

    # Fired when focus moves outside the dialog.
    on_focus_outside: EventHandler[no_args_event_spec]

    # Fired when the pointer interacts outside the dialog.
    on_interact_outside: EventHandler[no_args_event_spec]


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
