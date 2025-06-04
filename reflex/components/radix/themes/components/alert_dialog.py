"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.component import ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.components.radix.themes.base import (
    RadixThemesComponent,
    RadixThemesTriggerComponent,
)
from reflex.constants.compiler import MemoizationMode
from reflex.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex.vars.base import Var

LiteralContentSize = Literal["1", "2", "3", "4"]


class AlertDialogRoot(RadixThemesComponent):
    """Contains all the parts of the dialog."""

    tag = "AlertDialog.Root"

    # The controlled open state of the dialog.
    open: Var[bool]

    # Fired when the open state changes.
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # The open state of the dialog when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]


class AlertDialogTrigger(RadixThemesTriggerComponent):
    """Wraps the control that will open the dialog."""

    tag = "AlertDialog.Trigger"

    _memoization_mode = MemoizationMode(recursive=False)


class AlertDialogContent(elements.Div, RadixThemesComponent):
    """Contains the content of the dialog. This component is based on the div element."""

    tag = "AlertDialog.Content"

    # The size of the content.
    size: Var[Responsive[LiteralContentSize]]

    # Whether to force mount the content on open.
    force_mount: Var[bool]

    # Fired when the dialog is opened.
    on_open_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the dialog is closed.
    on_close_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[no_args_event_spec]


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
