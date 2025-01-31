"""Interactive components provided by @radix-ui/themes."""

from typing import Dict, Literal, Union

from reflex.components.component import ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.constants.compiler import MemoizationMode
from reflex.event import EventHandler, passthrough_event_spec
from reflex.vars.base import Var

from ..base import RadixThemesComponent, RadixThemesTriggerComponent


class HoverCardRoot(RadixThemesComponent):
    """For sighted users to preview content available behind a link."""

    tag = "HoverCard.Root"

    # The open state of the hover card when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # The controlled open state of the hover card. Must be used in conjunction with onOpenChange.
    open: Var[bool]

    # The duration from when the mouse enters the trigger until the hover card opens.
    open_delay: Var[int]

    # The duration from when the mouse leaves the trigger until the hover card closes.
    close_delay: Var[int]

    # Fired when the open state changes.
    on_open_change: EventHandler[passthrough_event_spec(bool)]


class HoverCardTrigger(RadixThemesTriggerComponent):
    """Wraps the link that will open the hover card."""

    tag = "HoverCard.Trigger"

    _memoization_mode = MemoizationMode(recursive=False)


class HoverCardContent(elements.Div, RadixThemesComponent):
    """Contains the content of the open hover card."""

    tag = "HoverCard.Content"

    # The preferred side of the trigger to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled.
    side: Var[Responsive[Literal["top", "right", "bottom", "left"]]]

    # The distance in pixels from the trigger.
    side_offset: Var[int]

    # The preferred alignment against the trigger. May change when collisions occur.
    align: Var[Literal["start", "center", "end"]]

    # An offset in pixels from the "start" or "end" alignment options.
    align_offset: Var[int]

    # Whether or not the hover card should avoid collisions with its trigger.
    avoid_collisions: Var[bool]

    # The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { top: 20, left: 20 }.
    collision_padding: Var[Union[float, int, Dict[str, Union[float, int]]]]

    # The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless
    sticky: Var[Literal["partial", "always"]]

    # Whether to hide the content when the trigger becomes fully occluded.
    hide_when_detached: Var[bool]

    # Hovercard size "1" - "3"
    size: Var[Responsive[Literal["1", "2", "3"]]]


class HoverCard(ComponentNamespace):
    """For sighted users to preview content available behind a link."""

    root = __call__ = staticmethod(HoverCardRoot.create)
    trigger = staticmethod(HoverCardTrigger.create)
    content = staticmethod(HoverCardContent.create)


hover_card = HoverCard()
