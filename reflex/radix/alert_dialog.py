"""The Radix alert dialog component."""
from reflex.components import Component
from reflex.vars import Var


class AlertDialogComponent(Component):
    """Base class for all alert dialog components."""

    library = "@radix-ui/react-alert-dialog"
    is_default = False


class AlertDialogRoot(AlertDialogComponent):
    """Radix alert dialog root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "AlertDialogRoot"

    default_open: Var[bool]
    open: Var[bool]


class AlertDialogTrigger(AlertDialogComponent):
    """Radix alert dialog trigger."""

    tag = "Trigger"
    alias = "AlertDialogTrigger"

    as_child: Var[bool]


class AlertDialogPortal(AlertDialogComponent):
    """Radix alert dialog portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "AlertDialogPortal"

    force_mount: Var[bool]


class AlertDialogOverlay(AlertDialogComponent):
    """Radix alert dialog overlay."""

    tag = "Overlay"
    alias = "AlertDialogOverlay"

    as_child: Var[bool]
    force_mount: Var[bool]


class AlertDialogContent(AlertDialogComponent):
    """Radix alert dialog content. Event handler props are not currently supported."""

    tag = "Content"
    alias = "AlertDialogContent"

    as_child: Var[bool]
    force_mount: Var[bool]


class AlertDialogCancel(AlertDialogComponent):
    """Radix alert dialog cancel."""

    tag = "Cancel"
    alias = "AlertDialogCancel"

    as_child: Var[bool]


class AlertDialogAction(AlertDialogComponent):
    """Radix alert dialog action."""

    tag = "Action"
    alias = "AlertDialogAction"

    as_child: Var[bool]


class AlertDialogTitle(AlertDialogComponent):
    """Radix alert dialog title."""

    tag = "Title"
    alias = "AlertDialogTitle"

    as_child: Var[bool]


class AlertDialogDescription(AlertDialogComponent):
    """Radix alert dialog description."""

    tag = "Description"
    alias = "AlertDialogDescription"

    as_child: Var[bool]
