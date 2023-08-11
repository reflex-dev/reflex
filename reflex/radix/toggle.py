"""Radix toggle component."""
from reflex.components import Component
from reflex.vars import Var


class ToggleRoot(Component):
    """Radix toggle root component. The onPressedChange prop is not currently supported."""

    library = "@radix-ui/react-toggle"
    is_default = False

    tag = "Root"
    alias = "ToggleRoot"

    as_child: Var[bool]
    pressed: Var[bool]
    default_pressed: Var[bool]
    disabled: Var[bool]
