"""The Radix dialog component."""
from typing import Optional

from reflex.components import Component


class DialogComponent(Component):
    """Base class for all dialog components."""

    library = "@radix-ui/react-dialog"
    is_default = False


class DialogRoot(DialogComponent):
    """Radix dialog root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "DialogRoot"

    default_open: Optional[bool]
    open: Optional[bool]
    modal: Optional[bool]


class DialogTrigger(DialogComponent):
    """Radix dialog trigger."""

    tag = "Trigger"
    alias = "DialogTrigger"

    as_child: Optional[bool]


class DialogPortal(DialogComponent):
    """Radix dialog portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "DialogPortal"

    force_mount: Optional[bool]


class DialogOverlay(DialogComponent):
    """Radix dialog overlay."""

    tag = "Overlay"
    alias = "DialogOverlay"

    as_child: Optional[bool]
    force_mount: Optional[bool]


class DialogContent(DialogComponent):
    """Radix dialog content. Event handler props are not currently supported."""

    tag = "Content"
    alias = "DialogContent"

    as_child: Optional[bool]
    force_mount: Optional[bool]


class DialogClose(DialogComponent):
    """Radix dialog close."""

    tag = "Close"
    alias = "DialogClose"

    as_child: Optional[bool]


class DialogTitle(DialogComponent):
    """Radix dialog title."""

    tag = "Title"
    alias = "DialogTitle"

    as_child: Optional[bool]


class DialogDescription(DialogComponent):
    """Radix dialog description."""

    tag = "Description"
    alias = "DialogDescription"

    as_child: Optional[bool]
