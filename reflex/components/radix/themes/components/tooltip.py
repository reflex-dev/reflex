"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Union

from reflex.components.component import Component
from reflex.constants import EventTriggers
from reflex.utils import format
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)

LiteralSideType = Literal[
    "top",
    "right",
    "bottom",
    "left",
]

LiteralAlignType = Literal[
    "start",
    "center",
    "end",
]

LiteralStickyType = Literal[
    "partial",
    "always",
]


# The Tooltip inherits props from the Tooltip.Root, Tooltip.Portal, Tooltip.Content
class Tooltip(RadixThemesComponent):
    """Floating element that provides a control with contextual information via pointer or focus."""

    tag = "Tooltip"

    # The content of the tooltip.
    content: Var[str]

    # The open state of the tooltip when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # The controlled open state of the tooltip. Must be used in conjunction with `on_open_change`.
    open: Var[bool]

    # The preferred side of the trigger to render against when open. Will be reversed when collisions occur and `avoid_collisions` is enabled.The position of the tooltip. Defaults to "top".
    side: Var[LiteralSideType]

    # The distance in pixels from the trigger. Defaults to 0.
    side_offset: Var[Union[float, int]]

    # The preferred alignment against the trigger. May change when collisions occur. Defaults to "center".
    align: Var[LiteralAlignType]

    # An offset in pixels from the "start" or "end" alignment options.
    align_offset: Var[Union[float, int]]

    # When true, overrides the side and align preferences to prevent collisions with boundary edges. Defaults to True.
    avoid_collisions: Var[bool]

    # The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { "top": 20, "left": 20 }. Defaults to 0.
    collision_padding: Var[Union[float, int, Dict[str, Union[float, int]]]]

    # The padding between the arrow and the edges of the content. If your content has border-radius, this will prevent it from overflowing the corners. Defaults to 0.
    arrow_padding: Var[Union[float, int]]

    # The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless. Defaults to "partial".
    sticky: Var[LiteralStickyType]

    # Whether to hide the content when the trigger becomes fully occluded. Defaults to False.
    hide_when_detached: Var[bool]

    # Override the duration in milliseconds to customize the open delay for a specific tooltip. Default is 700.
    delay_duration: Var[Union[float, int]]

    # Prevents Tooltip content from remaining open when hovering.
    disable_hoverable_content: Var[bool]

    # Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries.
    force_mount: Var[bool]

    # By default, screenreaders will announce the content inside the component. If this is not descriptive enough, or you have content that cannot be announced, use aria-label as a more descriptive label.
    aria_label: Var[str]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_OPEN_CHANGE: lambda e0: [e0.target.value],
            EventTriggers.ON_ESCAPE_KEY_DOWN: lambda e0: [e0.target.value],
            EventTriggers.ON_POINTER_DOWN_OUTSIDE: lambda e0: [e0.target.value],
        }

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Initialize the Tooltip component.

        Run some additional handling on the props.

        Args:
            *children: The positional arguments
            **props: The keyword arguments

        Returns:
            The created component.
        """
        ARIA_LABEL_KEY = "aria_label"
        if props.get(ARIA_LABEL_KEY) is not None:
            props[format.to_kebab_case(ARIA_LABEL_KEY)] = props.pop(ARIA_LABEL_KEY)

        return super().create(*children, **props)


tooltip = Tooltip.create
