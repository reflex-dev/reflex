"""Components using ComponentNamespace pattern.

This module tests:
- ComponentNamespace with __call__ = staticmethod(SomeComponent.create)
- Multiple components in the same module
- Namespace with staticmethod assignments
- Module-level namespace instance assignment
"""

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.vars.base import Var


class DialogRoot(Component):
    """The root dialog component."""

    # Whether the dialog is open.
    is_open: Var[bool] = field(doc="Whether the dialog is open.")


class DialogContent(Component):
    """The dialog content component."""

    # Whether to force mount the content.
    force_mount: Var[bool] = field(doc="Whether to force mount.")


class DialogTitle(Component):
    """The dialog title component."""

    # The title text.
    title_text: Var[str]


class Dialog(ComponentNamespace):
    """Dialog components namespace."""

    root = __call__ = staticmethod(DialogRoot.create)
    content = staticmethod(DialogContent.create)
    title = staticmethod(DialogTitle.create)


dialog = Dialog()
