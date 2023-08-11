"""The Radix dialog component."""
from reflex.components import Component
from reflex.vars import Var


class DialogComponent(Component):
    """Base class for all dialog components."""

    library = "@radix-ui/react-dialog"
    is_default = False


class DialogRoot(DialogComponent):
    """Radix dialog root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "DialogRoot"

    default_open: Var[bool]
    open: Var[bool]
    modal: Var[bool]


class DialogTrigger(DialogComponent):
    """Radix dialog trigger."""

    tag = "Trigger"
    alias = "DialogTrigger"

    as_child: Var[bool]


class DialogPortal(DialogComponent):
    """Radix dialog portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "DialogPortal"

    force_mount: Var[bool]


class DialogOverlay(DialogComponent):
    """Radix dialog overlay."""

    tag = "Overlay"
    alias = "DialogOverlay"

    as_child: Var[bool]
    force_mount: Var[bool]


class DialogContent(DialogComponent):
    """Radix dialog content. Event handler props are not currently supported."""

    tag = "Content"
    alias = "DialogContent"

    as_child: Var[bool]
    force_mount: Var[bool]


class DialogClose(DialogComponent):
    """Radix dialog close."""

    tag = "Close"
    alias = "DialogClose"

    as_child: Var[bool]


class DialogTitle(DialogComponent):
    """Radix dialog title."""

    tag = "Title"
    alias = "DialogTitle"

    as_child: Var[bool]


class DialogDescription(DialogComponent):
    """Radix dialog description."""

    tag = "Description"
    alias = "DialogDescription"

    as_child: Var[bool]
