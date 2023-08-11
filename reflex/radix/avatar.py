"""Radix Avatar components."""
from reflex.components import Component
from reflex.vars import Var


class AvatarComponent(Component):
    """Base class for all Avatar components."""

    library = "@radix-ui/react-avatar"

    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Var[bool]


class AvatarRoot(AvatarComponent):
    """Radix avatar root."""

    tag = "Root"
    alias = "AvatarRoot"


class AvatarImage(AvatarComponent):
    """Radix avatar image."""

    tag = "Image"
    alias = "AvatarImage"

    src: Var[str]
    alt: Var[str]


class AvatarFallback(AvatarComponent):
    """Radix avatar fallback."""

    tag = "Fallback"
    alias = "AvatarFallback"
