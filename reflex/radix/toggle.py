"""Radix toggle component."""
from typing import Optional

from reflex.components import Component


class ToggleRoot(Component):
    """Radix toggle root component. The onPressedChange prop is not currently supported."""

    library = "@radix-ui/react-toggle"
    is_default = False

    tag = "Root"
    alias = "ToggleRoot"

    as_child: Optional[bool]
    pressed: Optional[bool]
    default_pressed: Optional[bool]
    disabled: Optional[bool]
