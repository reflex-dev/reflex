"""Radix switch component."""
from reflex.components import Component
from reflex.vars import Var


class SwitchComponent(Component):
    """Base class for all switch components."""

    library = "@radix-ui/react-switch"
    is_default = False

    # Whether to use a child.
    as_child: Var[bool]


class SwitchRoot(SwitchComponent):
    """Radix switch root component. The onCheckedChange prop is not currently supported."""

    tag = "Root"
    alias = "SwitchRoot"

    default_checked: Var[bool]
    checked: Var[bool]
    disabled: Var[bool]
    required: Var[bool]
    name: Var[str]
    value: Var[str]


class SwitchThumb(SwitchComponent):
    """Radix switch thumb."""

    tag = "Thumb"
    alias = "SwitchThumb"
