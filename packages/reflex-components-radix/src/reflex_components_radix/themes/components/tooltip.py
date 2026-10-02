"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import Component, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.utils import format
from reflex_base.vars.base import Var

from reflex_components_radix.themes.base import RadixThemesComponent

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


ARIA_LABEL_KEY = "aria_label"


# The Tooltip inherits props from the Tooltip.Root, Tooltip.Portal, Tooltip.Content
class Tooltip(RadixThemesComponent):
    """Floating element that provides a control with contextual information via pointer or focus."""

    tag = "Tooltip"

    content: Var[str] = field(doc="The content of the tooltip.")

    default_open: Var[bool] = field(
        doc="The open state of the tooltip when it is initially rendered. Use when you do not need to control its open state."
    )

    open: Var[bool] = field(
        doc="The controlled open state of the tooltip. Must be used in conjunction with `on_open_change`."
    )

    side: Var[LiteralSideType] = field(
        doc='The preferred side of the trigger to render against when open. Will be reversed when collisions occur and `avoid_collisions` is enabled.The position of the tooltip. Defaults to "top".'
    )

    side_offset: Var[float | int] = field(
        doc="The distance in pixels from the trigger. Defaults to 0."
    )

    align: Var[LiteralAlignType] = field(
        doc='The preferred alignment against the trigger. May change when collisions occur. Defaults to "center".'
    )

    align_offset: Var[float | int] = field(
        doc='An offset in pixels from the "start" or "end" alignment options.'
    )

    avoid_collisions: Var[bool] = field(
        doc="When true, overrides the side and align preferences to prevent collisions with boundary edges. Defaults to True."
    )

    collision_padding: Var[float | int | dict[str, float | int]] = field(
        doc='The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { "top": 20, "left": 20 }. Defaults to 0.'
    )

    arrow_padding: Var[float | int] = field(
        doc="The padding between the arrow and the edges of the content. If your content has border-radius, this will prevent it from overflowing the corners. Defaults to 0."
    )

    sticky: Var[LiteralStickyType] = field(
        doc='The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless. Defaults to "partial".'
    )

    hide_when_detached: Var[bool] = field(
        doc="Whether to hide the content when the trigger becomes fully occluded. Defaults to False."
    )

    delay_duration: Var[float | int] = field(
        doc="Override the duration in milliseconds to customize the open delay for a specific tooltip. Default is 700."
    )

    disable_hoverable_content: Var[bool] = field(
        doc="Prevents Tooltip content from remaining open when hovering."
    )

    force_mount: Var[bool] = field(
        doc="Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries."
    )

    aria_label: Var[str] = field(
        doc="By default, screenreaders will announce the content inside the component. If this is not descriptive enough, or you have content that cannot be announced, use aria-label as a more descriptive label."
    )

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the tooltip."
    )

    _memoization_mode = MemoizationMode(recursive=False)

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
        if props.get(ARIA_LABEL_KEY) is not None:
            props[format.to_kebab_case(ARIA_LABEL_KEY)] = props.pop(ARIA_LABEL_KEY)

        return super().create(*children, **props)


tooltip = Tooltip.create
