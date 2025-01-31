"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.component import ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.constants.compiler import MemoizationMode
from reflex.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex.vars.base import Var

from ..base import RadixThemesComponent, RadixThemesTriggerComponent


class DialogRoot(RadixThemesComponent):
    """Root component for Dialog."""

    tag = "Dialog.Root"

    # The controlled open state of the dialog.
    open: Var[bool]

    # Fired when the open state changes.
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # The open state of the dialog when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]


class DialogTrigger(RadixThemesTriggerComponent):
    """Trigger an action or event, to open a Dialog modal."""

    tag = "Dialog.Trigger"

    _memoization_mode = MemoizationMode(recursive=False)


class DialogTitle(RadixThemesComponent):
    """Title component to display inside a Dialog modal."""

    tag = "Dialog.Title"


class DialogContent(elements.Div, RadixThemesComponent):
    """Content component to display inside a Dialog modal."""

    tag = "Dialog.Content"

    # DialogContent size "1" - "4"
    size: Var[Responsive[Literal["1", "2", "3", "4"]]]

    # Fired when the dialog is opened.
    on_open_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the dialog is closed.
    on_close_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[no_args_event_spec]

    # Fired when the pointer is down outside the dialog.
    on_pointer_down_outside: EventHandler[no_args_event_spec]

    # Fired when the pointer interacts outside the dialog.
    on_interact_outside: EventHandler[no_args_event_spec]


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
