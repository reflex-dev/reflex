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

LiteralContentSize = Literal["1", "2", "3", "4"]


class AlertDialogRoot(RadixThemesComponent):
    """Contains all the parts of the dialog."""

    tag = "AlertDialog.Root"

    open: Var[bool] = field(doc="The controlled open state of the dialog.")

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    default_open: Var[bool] = field(
        doc="The open state of the dialog when it is initially rendered. Use when you do not need to control its open state."
    )


class AlertDialogTrigger(RadixThemesTriggerComponent):
    """Wraps the control that will open the dialog."""

    tag = "AlertDialog.Trigger"

    _memoization_mode = MemoizationMode(recursive=False)


class AlertDialogContent(elements.Div, RadixThemesComponent):
    """Contains the content of the dialog. This component is based on the div element."""

    tag = "AlertDialog.Content"

    size: Var[Responsive[LiteralContentSize]] = field(doc="The size of the content.")

    force_mount: Var[bool] = field(doc="Whether to force mount the content on open.")

    on_open_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is opened."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )


class AlertDialogTitle(RadixThemesComponent):
    """An accessible title that is announced when the dialog is opened.
    This part is based on the Heading component with a pre-defined font size and
    leading trim on top.
    """

    tag = "AlertDialog.Title"


class AlertDialogDescription(RadixThemesComponent):
    """An optional accessible description that is announced when the dialog is opened.
    This part is based on the Text component with a pre-defined font size.
    """

    tag = "AlertDialog.Description"


class AlertDialogAction(RadixThemesTriggerComponent):
    """Wraps the control that will close the dialog. This should be distinguished
    visually from the Cancel control.
    """

    tag = "AlertDialog.Action"


class AlertDialogCancel(RadixThemesTriggerComponent):
    """Wraps the control that will close the dialog. This should be distinguished
    visually from the Action control.
    """

    tag = "AlertDialog.Cancel"


class AlertDialog(ComponentNamespace):
    """AlertDialog components namespace."""

    root = staticmethod(AlertDialogRoot.create)
    trigger = staticmethod(AlertDialogTrigger.create)
    content = staticmethod(AlertDialogContent.create)
    title = staticmethod(AlertDialogTitle.create)
    description = staticmethod(AlertDialogDescription.create)
    action = staticmethod(AlertDialogAction.create)
    cancel = staticmethod(AlertDialogCancel.create)


alert_dialog = AlertDialog()
