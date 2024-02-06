"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex import el
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import LiteralSize, RadixThemesComponent

LiteralSwitchSize = Literal["1", "2", "3", "4"]


class AlertDialogRoot(RadixThemesComponent):
    """Contains all the parts of the dialog."""

    tag = "AlertDialog.Root"

    # The controlled open state of the dialog.
    open: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_OPEN_CHANGE: lambda e0: [e0],
        }


class AlertDialogTrigger(RadixThemesComponent):
    """Wraps the control that will open the dialog."""

    tag = "AlertDialog.Trigger"


class AlertDialogContent(el.Div, RadixThemesComponent):
    """Contains the content of the dialog. This component is based on the div element."""

    tag = "AlertDialog.Content"

    # The size of the content.
    size: Var[LiteralSize]

    # Whether to force mount the content on open.
    force_mount: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_OPEN_AUTO_FOCUS: lambda e0: [e0],
            EventTriggers.ON_CLOSE_AUTO_FOCUS: lambda e0: [e0],
            EventTriggers.ON_ESCAPE_KEY_DOWN: lambda e0: [e0],
        }


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


class AlertDialogAction(RadixThemesComponent):
    """Wraps the control that will close the dialog. This should be distinguished
    visually from the Cancel control.
    """

    tag = "AlertDialog.Action"


class AlertDialogCancel(RadixThemesComponent):
    """Wraps the control that will close the dialog. This should be distinguished
    visually from the Action control.
    """

    tag = "AlertDialog.Cancel"
