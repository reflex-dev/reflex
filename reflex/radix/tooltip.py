"""Radix tooltip components."""
from typing import Dict, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class TooltipComponent(Component):
    """Base class for all tooltip components."""

    library = "@radix-ui/react-tooltip"
    is_default = False


class TooltipProvider(TooltipComponent):
    """Radix tooltip provider."""

    tag = "Provider"
    alias = "TooltipProvider"

    delay_duration: Var[int]
    skip_delay_duration: Var[int]
    disable_hoverable_content: Var[bool]


class TooltipRoot(TooltipComponent):
    """Radix tooltip root."""

    tag = "Root"
    alias = "TooltipRoot"

    open: Var[bool]
    default_open: Var[bool]
    on_open_change: Var[bool]
    delay_duration: Var[int]
    disable_hoverable_content: Var[bool]


class TooltipTrigger(TooltipComponent):
    """Radix tooltip trigger."""

    tag = "Trigger"
    alias = "TooltipTrigger"

    # Whether to use a child.
    as_child: Var[bool]


class TooltipPortal(TooltipComponent):
    """Radix tooltip portal. The container prop is not currently supported."""

    force_mount: Var[bool]


class TooltipContent(TooltipComponent):
    """Radix tooltip content. The aria-*, event handler, and collisionBoundary props are not currently supported."""

    as_child: Var[bool]
    force_mount: Var[bool]
    side: Var[Literal["top", "right", "bottom", "left"]]
    side_offset: Var[int]
    align: Var[Literal["start", "center", "end"]]
    align_offset: Var[int]
    avoid_collisions: Var[bool]
    collision_padding: Var[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Var[int]
    sticky: Var[Literal["always", "partial"]]
    hide_when_detached: Var[bool]


class TooltipArrow(TooltipComponent):
    """Radix tooltip arrow."""

    as_child: Var[bool]
    height: Var[int]
    width: Var[int]
