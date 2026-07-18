"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import (
    RadixThemesComponent,
    RadixThemesTriggerComponent,
)


class HoverCardRoot(RadixThemesComponent):
    """For sighted users to preview content available behind a link."""

    tag = "HoverCard.Root"

    default_open: Var[bool] = field(
        doc="The open state of the hover card when it is initially rendered. Use when you do not need to control its open state."
    )

    open: Var[bool] = field(
        doc="The controlled open state of the hover card. Must be used in conjunction with onOpenChange."
    )

    open_delay: Var[int] = field(
        doc="The duration from when the mouse enters the trigger until the hover card opens."
    )

    close_delay: Var[int] = field(
        doc="The duration from when the mouse leaves the trigger until the hover card closes."
    )

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )


class HoverCardTrigger(RadixThemesTriggerComponent):
    """Wraps the link that will open the hover card."""

    tag = "HoverCard.Trigger"

    _memoization_mode = MemoizationMode(recursive=False)


class HoverCardContent(elements.Div, RadixThemesComponent):
    """Contains the content of the open hover card."""

    tag = "HoverCard.Content"

    side: Var[Responsive[Literal["top", "right", "bottom", "left"]]] = field(
        doc="The preferred side of the trigger to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled."
    )

    side_offset: Var[int] = field(doc="The distance in pixels from the trigger.")

    align: Var[Literal["start", "center", "end"]] = field(
        doc="The preferred alignment against the trigger. May change when collisions occur."
    )

    align_offset: Var[int] = field(
        doc='An offset in pixels from the "start" or "end" alignment options.'
    )

    avoid_collisions: Var[bool] = field(
        doc="Whether or not the hover card should avoid collisions with its trigger."
    )

    collision_padding: Var[float | int | dict[str, float | int]] = field(
        doc="The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { top: 20, left: 20 }."
    )

    sticky: Var[Literal["partial", "always"]] = field(
        doc='The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless'
    )

    hide_when_detached: Var[bool] = field(
        doc="Whether to hide the content when the trigger becomes fully occluded."
    )

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='Hovercard size "1" - "3"'
    )


class HoverCard(ComponentNamespace):
    """For sighted users to preview content available behind a link."""

    root = __call__ = staticmethod(HoverCardRoot.create)
    trigger = staticmethod(HoverCardTrigger.create)
    content = staticmethod(HoverCardContent.create)


hover_card = HoverCard()
