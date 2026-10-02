"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import (
    RadixThemesComponent,
    RadixThemesTriggerComponent,
)


class DialogRoot(RadixThemesComponent):
    """Root component for Dialog."""

    tag = "Dialog.Root"

    open: Var[bool] = field(doc="The controlled open state of the dialog.")

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    default_open: Var[bool] = field(
        doc="The open state of the dialog when it is initially rendered. Use when you do not need to control its open state."
    )


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

    size: Var[Responsive[Literal["1", "2", "3", "4"]]] = field(
        doc='DialogContent size "1" - "4"'
    )

    on_open_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is opened."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the dialog."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer interacts outside the dialog."
    )


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
