from typing import Optional

from reflex.components.component import Component


class AvatarComponent(Component):
    library = "@radix-ui/react-avatar"

    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Optional[bool]


class AvatarRoot(AvatarComponent):
    tag = "Root"
    alias = "AvatarRoot"


class AvatarImage(AvatarComponent):
    tag = "Image"
    alias = "AvatarImage"


class AvatarFallback(AvatarComponent):
    tag = "Fallback"
    alias = "AvatarFallback"
