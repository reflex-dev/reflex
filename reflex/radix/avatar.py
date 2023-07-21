"""Radix Avatar components."""
from typing import Optional

from reflex.components import Component


class AvatarComponent(Component):
    """Base class for all Avatar components."""

    library = "@radix-ui/react-avatar"

    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Optional[bool]


class AvatarRoot(AvatarComponent):
    """Radix avatar root."""

    tag = "Root"
    alias = "AvatarRoot"


class AvatarImage(AvatarComponent):
    """Radix avatar image."""

    tag = "Image"
    alias = "AvatarImage"


class AvatarFallback(AvatarComponent):
    """Radix avatar fallback."""

    tag = "Fallback"
    alias = "AvatarFallback"
