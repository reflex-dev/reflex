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
    on_open_change: EventHandler[lambda e0: [e0]]


class HoverCardTrigger(RadixThemesTriggerComponent):
    """Wraps the link that will open the hover card."""

    tag = "HoverCard.Trigger"


class HoverCardContent(elements.Div, RadixThemesComponent):
    """Contains the content of the open hover card."""

    tag = "HoverCard.Content"

    # The preferred side of the trigger to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled.
    side: Var[Literal["top", "right", "bottom", "left"]]

    # The distance in pixels from the trigger.
    side_offset: Var[int]

    # The preferred alignment against the trigger. May change when collisions occur.
    align: Var[Literal["start", "center", "end"]]

    # Whether or not the hover card should avoid collisions with its trigger.
    avoid_collisions: Var[bool]


class HoverCard(ComponentNamespace):
    """For sighted users to preview content available behind a link."""

    root = __call__ = staticmethod(HoverCardRoot.create)
    trigger = staticmethod(HoverCardTrigger.create)
    content = staticmethod(HoverCardContent.create)


hover_card = HoverCard()
