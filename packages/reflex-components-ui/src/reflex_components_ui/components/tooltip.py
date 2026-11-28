"""A tooltip: a native ``popover`` that opens under the pointer and with the focus."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.base.fragment import Fragment

from reflex_components_ui.base import Part
from reflex_components_ui.components import _popup
from reflex_components_ui.components._group import choose, literal
from reflex_components_ui.components._popup import HoverContent, HoverTrigger
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.tooltip import ARROW, TOOLTIP

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

# How long the pointer rests on something before its tooltip opens, as in
# Radix Themes, and how long a tooltip waits for the pointer to reach it, in
# milliseconds.
_OPEN_DELAY = 200
_CLOSE_DELAY = 100


class TooltipTrigger(HoverTrigger):
    """What a tooltip describes: the child of the tooltip."""

    # A press on what a tooltip is on closes the tooltip.
    _heard: ClassVar[tuple[str, ...]] = (*HoverTrigger._heard, "onPointerDown")

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the trigger.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: the child, which its tooltip describes whether it is
            shown or not.
        """
        return (
            super()
            ._render(props)
            .add_props(**{"aria-describedby": self._popup.get("data-rx-hover")})
        )


class Tooltip(HoverContent):
    """Floating element that provides a control with contextual information via pointer or focus."""

    styles: ClassVar[ComponentStyles] = TOOLTIP

    _role: ClassVar[str | None] = "tooltip"

    # A tooltip is as far from what it describes as the one of Radix, which
    # has an arrow between the two.
    _gap: ClassVar[int] = ARROW

    content: Var[str] = field(doc="The content of the tooltip.")

    default_open: Var[bool] = field(
        doc="The open state of the tooltip when it is initially rendered. Use when you do not need to control its open state."
    )

    open: Var[bool] = field(
        doc="The controlled open state of the tooltip. Must be used in conjunction with `on_open_change`."
    )

    side: Var[LiteralSideType] = field(
        doc='The preferred side of the trigger to render against when open. Will be reversed when collisions occur and `avoid_collisions` is enabled. Defaults to "top".'
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

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Initialize the Tooltip component.

        Run some additional handling on the props.

        Args:
            *children: The positional arguments
            **props: The keyword arguments

        Returns:
            The created component: what the tooltip describes, then the
            tooltip, a popup that holds its text.
        """
        label = props.pop(ARIA_LABEL_KEY, None)
        if label is not None:
            props.setdefault("custom_attrs", {})["aria-label"] = label
        popup = super().create(
            Part.create(props.get("content"), part="text", tag="p"), **props
        )
        trigger = TooltipTrigger.create(*children)
        name = popup.id if popup.id is not None else f"rx-tooltip-{next(_popup._ids)}"
        popup._join(None, name, None)
        trigger._join(None, name, None)
        return Fragment.create(trigger, popup)

    def _join(self, root: Any, name: Any, on_open_change: Any) -> None:
        """Take the name of the tooltip, and what its script reads.

        Args:
            root: Nothing: a tooltip has no root.
            name: The id of the tooltip.
            on_open_change: Nothing: the tooltip has the event itself.
        """
        if self.id is None:
            self._popup["id"] = name
        self._open = self.open
        if self.default_open is not None:
            self._popup["data-default-open"] = self.default_open
        delay = self.delay_duration
        self._popup["data-open-delay"] = _OPEN_DELAY if delay is None else delay
        still = self.disable_hoverable_content
        self._popup["data-close-delay"] = (
            _CLOSE_DELAY if still is None else choose(literal(still), 0, _CLOSE_DELAY)
        )

    def _exclude_props(self) -> list[str]:
        """Keep the props that are no attributes off the element.

        Returns:
            The props read as styles, and what the tooltip hands its text
            and its script.
        """
        return [
            *super()._exclude_props(),
            "content",
            "default_open",
            "open",
            "arrow_padding",
            "delay_duration",
            "aria_label",
        ]


tooltip = Tooltip.create
