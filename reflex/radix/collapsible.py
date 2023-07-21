"""The Radix collapsible component."""
from typing import Optional

from reflex.components import Component


class CollapsibleComponent(Component):
    """Base class for all collapsible components."""

    library = "@radix-ui/react-collapsible"
    is_default = False

    # Whether to use a child.
    as_child: Optional[bool]


class CollapsibleRoot(CollapsibleComponent):
    """Radix collapsible root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "CollapsibleRoot"

    default_open: Optional[bool]
    open: Optional[bool]
    disabled: Optional[bool]


class CollapsibleTrigger(CollapsibleComponent):
    """Radix collapsible trigger."""

    tag = "Trigger"
    alias = "CollapsibleTrigger"


class CollapsibleContent(CollapsibleComponent):
    """Radix collapsible content."""

    tag = "Content"
    alias = "CollapsibleContent"

    force_mount: Optional[bool]
