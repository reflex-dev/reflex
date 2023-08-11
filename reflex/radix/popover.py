"""The Radix popover component."""
from typing import Dict, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class PopoverComponent(Component):
    """Base class for all popover components."""

    library = "@radix-ui/react-popover"
    is_default = False


class PopoverRoot(PopoverComponent):
    """Radix popover root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "PopoverRoot"

    default_open: Var[bool]
    open: Var[bool]
    modal: Var[bool]


class PopoverTrigger(PopoverComponent):
    """Radix popover trigger."""

    tag = "Trigger"
    alias = "PopoverTrigger"

    as_child: Var[bool]


class PopoverAnchor(PopoverComponent):
    """Radix popover anchor."""

    tag = "Anchor"
    alias = "PopoverAnchor"

    as_child: Var[bool]


class PopoverPortal(PopoverComponent):
    """Radix popover portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "PopoverPortal"

    force_mount: Var[bool]


class PopoverContent(PopoverComponent):
    """Radix popover content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "PopoverContent"

    as_child: Var[bool]
    force_mount: Var[bool]
    side: Var[Literal["top", "right", "bottom", "left"]]
    side_offset: Var[int]
    align: Var[Literal["start", "center", "end"]]
    alignOffset: Var[int]
    avoid_collisions: Var[bool]
    collision_padding: Var[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Var[int]
    sticky: Var[Literal["partial", "always"]]
    hide_when_detached: Var[bool]


class PopoverArrow(PopoverComponent):
    """Radix popover arrow."""

    tag = "Arrow"
    alias = "PopoverArrow"

    as_child: Var[bool]
    width: Var[int]
    height: Var[int]


class PopoverClose(PopoverComponent):
    """Radix popover close."""

    tag = "Close"
    alias = "PopoverClose"

    as_child: Var[bool]
