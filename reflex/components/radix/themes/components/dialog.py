"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.component import ComponentNamespace
from reflex.components.el import elements
from reflex.event import EventHandler
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
    RadixThemesTriggerComponent,
)


class DialogRoot(RadixThemesComponent):
    """Root component for Dialog."""

    tag = "Dialog.Root"

    # The controlled open state of the dialog.
    open: Var[bool]

    # Fired when the open state changes.
    on_open_change: EventHandler[lambda e0: [e0]]


class DialogTrigger(RadixThemesTriggerComponent):
    """Trigger an action or event, to open a Dialog modal."""

    tag = "Dialog.Trigger"


class DialogTitle(RadixThemesComponent):
    """Title component to display inside a Dialog modal."""

    tag = "Dialog.Title"


class DialogContent(elements.Div, RadixThemesComponent):
    """Content component to display inside a Dialog modal."""

    tag = "Dialog.Content"

    # DialogContent size "1" - "4"
    size: Var[Literal["1", "2", "3", "4"]]

    # Fired when the dialog is opened.
    on_open_auto_focus: EventHandler[lambda e0: [e0]]

    # Fired when the dialog is closed.
    on_close_auto_focus: EventHandler[lambda e0: [e0]]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[lambda e0: [e0]]

    # Fired when the pointer is down outside the dialog.
    on_pointer_down_outside: EventHandler[lambda e0: [e0]]

    # Fired when the pointer interacts outside the dialog.
    on_interact_outside: EventHandler[lambda e0: [e0]]


class DialogDescription(RadixThemesComponent):
    """Description component to display inside a Dialog modal."""

    tag = "Dialog.Description"


class DialogClose(RadixThemesTriggerComponent):
    """Close button component to close an open Dialog modal."""

    tag = "Dialog.Close"


class Dialog(ComponentNamespace):
    """Dialog components namespace."""

    root = __call__ = staticmethod(DialogRoot.create)
    trigger = staticmethod(DialogTrigger.create)
    title = staticmethod(DialogTitle.create)
    content = staticmethod(DialogContent.create)
    description = staticmethod(DialogDescription.create)
    close = staticmethod(DialogClose.create)


dialog = Dialog()
