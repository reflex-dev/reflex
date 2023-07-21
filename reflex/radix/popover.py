"""The Radix popover component."""
from typing import Dict, Literal, Optional, Union

from reflex.components import Component


class PopoverComponent(Component):
    """Base class for all popover components."""

    library = "@radix-ui/react-popover"
    is_default = False


class PopoverRoot(PopoverComponent):
    """Radix popover root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "PopoverRoot"

    default_open: Optional[bool]
    open: Optional[bool]
    modal: Optional[bool]


class PopoverTrigger(PopoverComponent):
    """Radix popover trigger."""

    tag = "Trigger"
    alias = "PopoverTrigger"

    as_child: Optional[bool]


class PopoverAnchor(PopoverComponent):
    """Radix popover anchor."""

    tag = "Anchor"
    alias = "PopoverAnchor"

    as_child: Optional[bool]


class PopoverPortal(PopoverComponent):
    """Radix popover portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "PopoverPortal"

    force_mount: Optional[bool]


class PopoverContent(PopoverComponent):
    """Radix popover content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "PopoverContent"

    as_child: Optional[bool]
    force_mount: Optional[bool]
    side: Optional[Literal["top", "right", "bottom", "left"]]
    side_offset: Optional[int]
    align: Optional[Literal["start", "center", "end"]]
    alignOffset: Optional[int]
    avoid_collisions: Optional[bool]
    collision_padding: Optional[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Optional[int]
    sticky: Optional[Literal["partial", "always"]]
    hide_when_detached: Optional[bool]


class PopoverArrow(PopoverComponent):
    """Radix popover arrow."""

    tag = "Arrow"
    alias = "PopoverArrow"

    as_child: Optional[bool]
    width: Optional[int]
    height: Optional[int]


class PopoverClose(PopoverComponent):
    """Radix popover close."""

    tag = "Close"
    alias = "PopoverClose"

    as_child: Optional[bool]
