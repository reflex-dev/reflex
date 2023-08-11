"""The Radix collapsible component."""
from reflex.components import Component
from reflex.vars import Var


class CollapsibleComponent(Component):
    """Base class for all collapsible components."""

    library = "@radix-ui/react-collapsible"
    is_default = False

    # Whether to use a child.
    as_child: Var[bool]


class CollapsibleRoot(CollapsibleComponent):
    """Radix collapsible root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "CollapsibleRoot"

    default_open: Var[bool]
    open: Var[bool]
    disabled: Var[bool]


class CollapsibleTrigger(CollapsibleComponent):
    """Radix collapsible trigger."""

    tag = "Trigger"
    alias = "CollapsibleTrigger"


class CollapsibleContent(CollapsibleComponent):
    """Radix collapsible content."""

    tag = "Content"
    alias = "CollapsibleContent"

    force_mount: Var[bool]
