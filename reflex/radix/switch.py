"""Radix switch component."""
from typing import Optional

from reflex.components import Component


class SwitchComponent(Component):
    """Base class for all switch components."""

    library = "@radix-ui/react-switch"

    is_default = False

    # Whether to use a child.
    as_child: Optional[bool]


class SwitchRoot(SwitchComponent):
    """Radix switch root component. The onCheckedChange prop is not currently supported."""

    tag = "Root"
    alias = "SwitchRoot"

    default_checked: Optional[bool]
    checked: Optional[bool]
    disabled: Optional[bool]
    required: Optional[bool]
    name: Optional[str]
    value: Optional[str]


class SwitchThumb(SwitchComponent):
    """Radix switch thumb."""

    tag = "Thumb"
    alias = "SwitchThumb"
