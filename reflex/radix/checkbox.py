"""The Radix checkbox component."""
from reflex.components import Component
from reflex.vars import Var


class CheckboxComponent(Component):
    """Base class for all checkbox components."""

    library = "@radix-ui/react-checkbox"
    is_default = False

    # Whether to use a child.
    as_child: Var[bool]


class CheckboxRoot(CheckboxComponent):
    """Radix checkbox root. The onCheckedChange prop is not currently supported."""

    tag = "Root"
    alias = "CheckboxRoot"

    default_checked: Var[bool]
    checked: Var[bool]
    disabled: Var[bool]
    required: Var[bool]
    name: Var[str]
    value: Var[str]


class CheckboxIndicator(CheckboxComponent):
    """Radix checkbox indicator."""

    tag = "Indicator"
    alias = "CheckboxIndicator"

    force_mount: Var[bool]
