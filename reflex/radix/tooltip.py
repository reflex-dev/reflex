"""Radix tooltip components."""
from typing import Dict, Literal, Optional, Union

from reflex.components import Component


class TooltipComponent(Component):
    """Base class for all tooltip components."""

    library = "@radix-ui/react-tooltip"

    is_default = False


class TooltipProvider(TooltipComponent):
    """Radix tooltip provider."""

    tag = "Provider"
    alias = "TooltipProvider"

    delay_duration: Optional[int]
    skip_delay_duration: Optional[int]
    disable_hoverable_content: Optional[bool]


class TooltipRoot(TooltipComponent):
    """Radix tooltip root."""

    tag = "Root"
    alias = "TooltipRoot"

    open: Optional[bool]
    default_open: Optional[bool]
    on_open_change: Optional[bool]
    delay_duration: Optional[int]
    disable_hoverable_content: Optional[bool]


class TooltipTrigger(TooltipComponent):
    """Radix tooltip trigger."""

    tag = "Trigger"
    alias = "TooltipTrigger"

    # Whether to use a child.
    as_child: Optional[bool]


class TooltipPortal(TooltipComponent):
    """Radix tooltip portal. The container prop is not currently supported."""

    force_mount: Optional[bool]


class TooltipContent(TooltipComponent):
    """Radix tooltip content. The aria-*, event handler, and collisionBoundary props are not currently supported."""

    as_child: Optional[bool]
    force_mount: Optional[bool]
    side: Optional[Literal["top", "right", "bottom", "left"]]
    side_offset: Optional[int]
    align: Optional[Literal["start", "center", "end"]]
    align_offset: Optional[int]
    avoid_collisions: Optional[bool]
    collision_padding: Optional[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Optional[int]
    sticky: Optional[Literal["always", "partial"]]
    hide_when_detached: Optional[bool]


class TooltipArrow(TooltipComponent):
    """Radix tooltip arrow."""

    as_child: Optional[bool]
    height: Optional[int]
    width: Optional[int]
