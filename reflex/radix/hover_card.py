"""The Radix hover card component."""
from typing import Dict, Literal, Optional, Union

from reflex.components import Component


class HoverCardComponent(Component):
    """Base class for all hover card components."""

    library = "@radix-ui/react-hover-card"
    is_default = False


class HoverCardRoot(HoverCardComponent):
    """Radix hover card root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "HoverCardRoot"

    default_open: Optional[bool]
    open: Optional[bool]
    open_delay: Optional[int]
    close_delay: Optional[int]


class HoverCardTrigger(HoverCardComponent):
    """Radix hover card trigger."""

    tag = "Trigger"
    alias = "HoverCardTrigger"

    as_child: Optional[bool]


class HoverCardPortal(HoverCardComponent):
    """Radix hover card portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "HoverCardPortal"

    force_mount: Optional[bool]


class HoverCardContent(HoverCardComponent):
    """Radix hover card content. The collisionBoundary prop is not currently supported."""

    tag = "Content"
    alias = "HoverCardContent"

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
    sticky: Optional[Literal["partial", "always"]]
    hide_when_detached: Optional[bool]


class HoverCardArrow(HoverCardComponent):
    """Radix hover card arrow."""

    tag = "Arrow"
    alias = "HoverCardArrow"

    as_child: Optional[bool]
    width: Optional[int]
    height: Optional[int]
