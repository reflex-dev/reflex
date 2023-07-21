"""The Radix checkbox component."""
from typing import Optional

from reflex.components import Component


class CheckboxComponent(Component):
    """Base class for all checkbox components."""

    library = "@radix-ui/react-checkbox"
    is_default = False

    # Whether to use a child.
    as_child: Optional[bool]


class CheckboxRoot(Component):
    """Radix checkbox root. The onCheckedChange prop is not currently supported."""

    tag = "Root"
    alias = "CheckboxRoot"

    default_checked: Optional[bool]
    checked: Optional[bool]
    disabled: Optional[bool]
    required: Optional[bool]
    name: Optional[str]
    value: Optional[str]


class CheckboxIndicator(Component):
    """Radix checkbox indicator."""

    tag = "Indicator"
    alias = "CheckboxIndicator"

    force_mount: Optional[bool]
