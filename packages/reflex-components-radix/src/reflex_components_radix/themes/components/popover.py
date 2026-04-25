"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import (
    RadixThemesComponent,
    RadixThemesTriggerComponent,
)


class PopoverRoot(RadixThemesComponent):
    """Floating element for displaying rich content, triggered by a button."""

    tag = "Popover.Root"

    open: Var[bool] = field(doc="The controlled open state of the popover.")

    modal: Var[bool] = field(
        doc="The modality of the popover. When set to true, interaction with outside elements will be disabled and only popover content will be visible to screen readers."
    )

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    default_open: Var[bool] = field(
        doc="The open state of the popover when it is initially rendered. Use when you do not need to control its open state."
    )


class PopoverTrigger(RadixThemesTriggerComponent):
    """Wraps the control that will open the popover."""

    tag = "Popover.Trigger"

    _memoization_mode = MemoizationMode(recursive=False)


class PopoverContent(elements.Div, RadixThemesComponent):
    """Contains content to be rendered in the open popover."""

    tag = "Popover.Content"

    size: Var[Responsive[Literal["1", "2", "3", "4"]]] = field(
        doc='Size of the button: "1" | "2" | "3" | "4"'
    )

    side: Var[Literal["top", "right", "bottom", "left"]] = field(
        doc="The preferred side of the anchor to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled."
    )

    side_offset: Var[int] = field(doc="The distance in pixels from the anchor.")

    align: Var[Literal["start", "center", "end"]] = field(
        doc="The preferred alignment against the anchor. May change when collisions occur."
    )

    align_offset: Var[int] = field(
        doc="The vertical distance in pixels from the anchor."
    )

    avoid_collisions: Var[bool] = field(
        doc="When true, overrides the side andalign preferences to prevent collisions with boundary edges."
    )

    collision_padding: Var[float | int | dict[str, float | int]] = field(
        doc='The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { "top": 20, "left": 20 }. Defaults to 0.'
    )

    sticky: Var[Literal["partial", "always"]] = field(
        doc='The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless. Defaults to "partial".'
    )

    hide_when_detached: Var[bool] = field(
        doc="Whether to hide the content when the trigger becomes fully occluded. Defaults to False."
    )

    on_open_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is opened."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the dialog."
    )

    on_focus_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when focus moves outside the dialog."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer interacts outside the dialog."
    )


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
