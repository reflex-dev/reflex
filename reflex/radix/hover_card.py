"""The Radix hover card component."""
from typing import Dict, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class HoverCardComponent(Component):
    """Base class for all hover card components."""

    library = "@radix-ui/react-hover-card"
    is_default = False


class HoverCardRoot(HoverCardComponent):
    """Radix hover card root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "HoverCardRoot"

    default_open: Var[bool]
    open: Var[bool]
    open_delay: Var[int]
    close_delay: Var[int]


class HoverCardTrigger(HoverCardComponent):
    """Radix hover card trigger."""

    tag = "Trigger"
    alias = "HoverCardTrigger"

    as_child: Var[bool]


class HoverCardPortal(HoverCardComponent):
    """Radix hover card portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "HoverCardPortal"

    force_mount: Var[bool]


class HoverCardContent(HoverCardComponent):
    """Radix hover card content. The collisionBoundary prop is not currently supported."""

    tag = "Content"
    alias = "HoverCardContent"

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
    sticky: Var[Literal["partial", "always"]]
    hide_when_detached: Var[bool]


class HoverCardArrow(HoverCardComponent):
    """Radix hover card arrow."""

    tag = "Arrow"
    alias = "HoverCardArrow"

    as_child: Var[bool]
    width: Var[int]
    height: Var[int]
